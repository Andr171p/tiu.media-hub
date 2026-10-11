"""Opt-in integration check: a disposable Keycloak container, real PKCE and Client Credentials.

Run: uv run python -m tests.check_keycloak
Requires Docker and the project's Keycloak image. No existing realm or database is changed.
"""

import asyncio
import base64
import hashlib
import os
import secrets
import shutil
import socket
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- Disposable Docker test harness.
from html.parser import HTMLParser
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import aiohttp
import uvicorn

from main import create_app
from src.core.auth.models import Client
from src.core.keycloak.client import KeycloakClient
from src.core.keycloak.config import KeycloakConfig
from src.core.services.base import SrvBaseClient, SrvBaseConfig

KEYCLOAK_URL = "http://localhost:18081"
REALM_URL = f"{KEYCLOAK_URL}/realms/tiu-media-hub"
IMAGE = "quay.io/keycloak/keycloak:26.7.0"


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.messages = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "style"}:
            self.in_script = True
        if tag == "form" and attributes.get("id") == "kc-form-login":
            self.action = attributes["action"]

    def handle_data(self, data):
        if not self.in_script and data.strip():
            self.messages.append(data.strip())

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.in_script = False


async def wait_keycloak(http: aiohttp.ClientSession) -> None:
    for _ in range(90):
        try:
            async with http.get(f"{REALM_URL}/.well-known/openid-configuration") as response:
                if response.status == HTTPStatus.OK:
                    break
        except aiohttp.ClientError, TimeoutError:
            pass
        await asyncio.sleep(1)
    else:
        raise RuntimeError("Disposable Keycloak did not become ready.")


async def provision(http: aiohttp.ClientSession, admin_password: str) -> tuple[str, str, str]:
    async with http.post(
        f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": "integration-admin",
            "password": admin_password,
        },
    ) as response:
        response.raise_for_status()
        admin_token = (await response.json())["access_token"]

    admin_url = f"{KEYCLOAK_URL}/admin/realms/tiu-media-hub"
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    async with http.get(f"{admin_url}/clients", headers=admin_headers) as response:
        response.raise_for_status()
        clients = {client["clientId"]: client["id"] for client in await response.json()}
    async with http.get(
        f"{admin_url}/clients/{clients['tiu-media-hub-worker']}/client-secret",
        headers=admin_headers,
    ) as response:
        response.raise_for_status()
        worker_secret = (await response.json())["value"]

    password = secrets.token_urlsafe(32)
    async with http.post(
        f"{admin_url}/users",
        headers=admin_headers,
        json={
            "username": "auth-test",
            "enabled": True,
            "email": "auth-test@example.com",
            "firstName": "Auth",
            "lastName": "Test",
            "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        },
    ) as response:
        response.raise_for_status()
        user_id = response.headers["Location"].rsplit("/", 1)[1]
    async with http.get(
        f"{admin_url}/clients/{clients['tiu-media-hub-api']}/roles/creator", headers=admin_headers
    ) as response:
        response.raise_for_status()
        user_role = await response.json()
    async with http.post(
        f"{admin_url}/users/{user_id}/role-mappings/clients/{clients['tiu-media-hub-api']}",
        headers=admin_headers,
        json=[user_role],
    ) as response:
        response.raise_for_status()
    return worker_secret, user_id, password


async def login_pkce(http: aiohttp.ClientSession, password: str) -> dict[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    state = secrets.token_urlsafe(24)
    redirect_uri = "http://localhost:5173/callback"
    authorize_url = f"{REALM_URL}/protocol/openid-connect/auth?" + urlencode({
        "client_id": "tiu-media-hub-web",
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    async with http.get(authorize_url) as response:
        response.raise_for_status()
        form = LoginForm()
        form.feed(await response.text())
    assert form.action, "Keycloak login form not found"
    async with http.post(
        form.action,
        data={"username": "auth-test", "password": password},
        headers={"Origin": KEYCLOAK_URL, "Referer": authorize_url},
        allow_redirects=False,
    ) as response:
        if response.status != HTTPStatus.FOUND:
            failed_form = LoginForm()
            failed_form.feed(await response.text())
            raise RuntimeError(f"Login failed: HTTP {response.status}; {failed_form.messages}")
        query = parse_qs(urlsplit(response.headers["Location"]).query)
        assert query["state"] == [state]
        code = query["code"][0]
    async with http.post(
        f"{REALM_URL}/protocol/openid-connect/token",
        data={
            "grant_type": "authorization_code",
            "client_id": "tiu-media-hub-web",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    ) as response:
        response.raise_for_status()
        user_tokens = await response.json()
    return {name: user_tokens[name] for name in ("access_token", "id_token")}


async def check_api(
    http: aiohttp.ClientSession,
    worker_secret: str,
    user_id: str,
    user_tokens: dict[str, str],
    password: str,
) -> None:
    config = KeycloakConfig(
        issuer_url=REALM_URL, jwks_url=f"{REALM_URL}/protocol/openid-connect/certs"
    )
    verifier_client = KeycloakClient(config)
    try:
        await verifier_client.verify_token(user_tokens["access_token"])
    finally:
        await verifier_client.close()
    app = create_app(config)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        api_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("API startup failed.")
                await asyncio.sleep(0.05)
            async with SrvBaseClient(
                SrvBaseConfig(
                    base_url=f"{api_url}/api/v1/",
                    token_url=f"{REALM_URL}/protocol/openid-connect/token",
                    client_id="tiu-media-hub-worker",
                    client_secret=worker_secret,
                )
            ) as worker:
                principal = await worker.request_json("GET", "auth/me", Client)
                assert principal.client_id == "tiu-media-hub-worker"
                assert principal.roles == frozenset({"assets:read", "collections:read"})
            async with http.get(
                f"{api_url}/api/v1/users/me",
                headers={"Authorization": f"Bearer {user_tokens['access_token']}"},
            ) as response:
                assert response.status == HTTPStatus.OK
                user = await response.json()
                assert user["id"] == user_id
                assert user["type"] == "creator"
                assert user["roles"] == ["creator"]
            async with http.get(
                f"{api_url}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {user_tokens['id_token']}"},
            ) as response:
                assert response.status == HTTPStatus.UNAUTHORIZED, (
                    "ID tokens must not authorize API calls"
                )
            async with http.post(
                f"{REALM_URL}/protocol/openid-connect/token",
                data={
                    "client_id": "tiu-media-hub-web",
                    "grant_type": "password",
                    "username": "auth-test",
                    "password": password,
                },
            ) as response:
                assert response.status == HTTPStatus.BAD_REQUEST, (
                    "Password grant must remain disabled for the SPA"
                )
        finally:
            server.should_exit = True
            await serving


async def check_flows(admin_password: str) -> None:
    # Match the browser treatment of localhost for Keycloak's secure login cookies.
    cookies = aiohttp.CookieJar(treat_as_secure_origin=KEYCLOAK_URL)
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10),
        cookie_jar=cookies,
    ) as http:
        await wait_keycloak(http)
        worker_secret, user_id, password = await provision(http, admin_password)
        tokens = await login_pkce(http, password)
        await check_api(http, worker_secret, user_id, tokens, password)


def main() -> None:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker is required for this integration check.")
    container_name = f"tiu-auth-check-{uuid4().hex[:12]}"
    realm_dir = Path(__file__).resolve().parents[1] / "keycloak" / "realm"
    password = secrets.token_urlsafe(32)
    environment = dict(
        os.environ,
        KC_BOOTSTRAP_ADMIN_USERNAME="integration-admin",
        KC_BOOTSTRAP_ADMIN_PASSWORD=password,
    )
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- Fixed Docker arguments, shell disabled.
        [
            docker,
            "run",
            "--detach",
            "--rm",
            "--name",
            container_name,
            "--publish",
            "127.0.0.1:18081:8080",
            "--mount",
            f"type=bind,source={realm_dir},target=/opt/keycloak/data/import,readonly",
            "--env",
            "KC_BOOTSTRAP_ADMIN_USERNAME",
            "--env",
            "KC_BOOTSTRAP_ADMIN_PASSWORD",
            IMAGE,
            "start-dev",
            "--import-realm",
            "--hostname",
            KEYCLOAK_URL,
        ],
        check=True,
        capture_output=True,
        env=environment,
        timeout=60,
    )
    try:
        asyncio.run(check_flows(password))
        print(  # ruff: ignore[print] -- CLI check result, contains no credentials.
            "PASS: real PKCE login, service Client Credentials, API roles, "
            "ID-token rejection, disabled password grant."
        )
    finally:
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- Only this check's generated container name.
            [docker, "rm", "--force", container_name],
            check=True,
            capture_output=True,
            timeout=30,
        )


if __name__ == "__main__":
    main()
