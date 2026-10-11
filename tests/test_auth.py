import asyncio
import json
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
import jwt
from aiohttp import web
from aiohttp.test_utils import TestServer
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import TypeAdapter, ValidationError

from main import create_app
from src.core.auth.models import Auth, Client, User
from src.core.auth.exceptions import AuthenticationError, AuthenticationUnavailableError
from src.core.keycloak.client import KeycloakClient
from src.core.keycloak.config import KeycloakConfig
from src.modules.keycloak import get_keycloak_client


class KeycloakTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    async def asyncSetUp(self):
        self.jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        self.jwk.update(kid="first", alg="RS256", use="sig")
        self.keys = [self.jwk]
        self.calls = 0
        self.jwks_status = 200
        application = web.Application()
        application.router.add_get("/certs", self.serve_keys)
        self.server = TestServer(application)
        await self.server.start_server()
        self.addAsyncCleanup(self.server.close)
        self.config = KeycloakConfig(
            jwks_url=str(self.server.make_url("/certs")),
            clock_skew=0,
        )
        self.client = KeycloakClient(self.config)
        self.addAsyncCleanup(self.client.close)
        self.subject = uuid4()

    async def serve_keys(self, _request):
        self.calls += 1
        await asyncio.sleep(0)
        return web.json_response({"keys": self.keys}, status=self.jwks_status)

    def token(self, *, changes=None, remove=(), kid="first", private_key=None):
        payload = {
            "iss": str(self.config.issuer_url),
            "aud": self.config.audience,
            "sub": str(self.subject),
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "azp": "tiu-media-hub-web",
            "typ": "Bearer",
            "auth_type": "creator",
            "preferred_username": "alice",
            "name": "Alice Example",
            "email": "alice@example.com",
            "email_verified": True,
            "resource_access": {
                self.config.audience: {"roles": ["creator"]},
                "another-api": {"roles": ["admin"]},
            },
            "realm_access": {"roles": ["admin"]},
        }
        payload.update(changes or {})
        for claim in remove:
            payload.pop(claim, None)
        return jwt.encode(
            payload, private_key or self.private_key, algorithm="RS256", headers={"kid": kid}
        )

    async def test_user_claims_and_role_isolation(self):
        user = await self.client.verify_token(self.token())
        self.assertIsInstance(user, User)
        self.assertEqual(user.id, self.subject)
        self.assertEqual(user.roles, frozenset({"creator"}))
        self.assertEqual(user.full_name, "Alice Example")
        self.assertTrue(user.email_verified)
        with self.assertRaises(ValidationError):
            user.username = "changed"

    async def test_client_uses_azp_not_subject_uuid(self):
        principal = await self.client.verify_token(
            self.token(
                changes={
                    "auth_type": "client",
                    "azp": "tiu-media-hub-worker",
                    "sub": "service-subject",
                }
            )
        )
        self.assertIsInstance(principal, Client)
        self.assertEqual(principal.client_id, "tiu-media-hub-worker")
        self.assertNotIn("id", principal.model_dump())

    async def test_username_is_not_a_service_discriminator(self):
        user = await self.client.verify_token(
            self.token(
                changes={
                    "preferred_username": "service-account-fake",
                }
            )
        )
        self.assertIsInstance(user, User)

    async def test_missing_optional_profile(self):
        user = await self.client.verify_token(
            self.token(
                remove=(
                    "preferred_username",
                    "email",
                    "email_verified",
                    "name",
                    "resource_access",
                )
            )
        )
        self.assertIsNone(user.email)
        self.assertFalse(user.email_verified)
        self.assertFalse(user.roles)

    async def test_reject_invalid_claims(self):
        invalid = [
            {"iss": "https://untrusted.example/realm"},
            {"aud": "another-api"},
            {"exp": int(time.time()) - 20},
            {"iat": int(time.time()) + 60},
            {"nbf": int(time.time()) + 60},
            {"sub": "not-a-uuid"},
            {"sub": ""},
            {"sub": 123},
            {"typ": "ID"},
            {"typ": "Refresh"},
            {"azp": "unknown"},
            {"auth_type": "client"},
            {"azp": "tiu-media-hub-worker"},
            {"auth_type": "admin"},
            {"email": "malformed"},
            {"email_verified": "true"},
            {"resource_access": {self.config.audience: {"roles": "admin"}}},
            {"resource_access": {self.config.audience: {"roles": [123]}}},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(AuthenticationError):
                await self.client.verify_token(self.token(changes=changes))

    async def test_required_claims(self):
        for claim in ("exp", "iat", "iss", "aud", "sub", "azp", "typ", "auth_type"):
            with self.subTest(claim=claim), self.assertRaises(AuthenticationError):
                await self.client.verify_token(self.token(remove=(claim,)))

    async def test_signature_and_algorithm_rejection(self):
        with self.assertRaises(AuthenticationError):
            await self.client.verify_token(self.token(private_key=self.other_key))
        for token in (
            "not-a-jwt",
            jwt.encode({"sub": "x"}, "x" * 32, algorithm="HS256", headers={"kid": "first"}),
        ):
            with self.assertRaises(AuthenticationError):
                await self.client.verify_token(token)

    async def test_concurrent_verification_fetches_jwks_once(self):
        token = self.token()
        await asyncio.gather(*(self.client.verify_token(token) for _ in range(20)))
        self.assertEqual(self.calls, 1)

    async def test_rotation_refreshes_fresh_cache_and_deduplicates(self):
        await self.client.verify_token(self.token())
        self.keys = [dict(self.jwk, kid="rotated")]
        rotated = self.token(kid="rotated")
        with patch("src.core.keycloak.client.monotonic", return_value=time.monotonic() + 6):
            await asyncio.gather(*(self.client.verify_token(rotated) for _ in range(20)))
        self.assertEqual(self.calls, 2)

    async def test_unknown_kid_requests_are_bounded(self):
        await self.client.verify_token(self.token())
        for index in range(20):
            with self.assertRaises(AuthenticationError):
                await self.client.verify_token(self.token(kid=f"unknown-{index}"))
        self.assertEqual(self.calls, 2)

    async def test_expired_cache_is_refreshed_for_known_kid(self):
        token = self.token()
        await self.client.verify_token(token)
        with patch("src.core.keycloak.client.monotonic", return_value=time.monotonic() + 301):
            await self.client.verify_token(token)
        self.assertEqual(self.calls, 2)

    async def test_jwks_outage_and_recovery(self):
        self.jwks_status = 503
        for _ in range(2):
            with self.assertRaises(AuthenticationUnavailableError):
                await self.client.verify_token(self.token())
        self.assertEqual(self.calls, 1)
        self.jwks_status = 200
        with patch("src.core.keycloak.client.monotonic", return_value=time.monotonic() + 6):
            await self.client.verify_token(self.token())
        self.assertEqual(self.calls, 2)

    async def test_invalid_jwks_is_dependency_error(self):
        self.keys = [dict(self.jwk, n=None)]
        with self.assertRaises(AuthenticationUnavailableError):
            await self.client.verify_token(self.token())

    async def test_cached_key_survives_short_outage_but_expired_cache_does_not(self):
        token = self.token()
        await self.client.verify_token(token)
        self.jwks_status = 503
        await self.client.verify_token(token)
        with (
            patch("src.core.keycloak.client.monotonic", return_value=time.monotonic() + 301),
            self.assertRaises(AuthenticationUnavailableError),
        ):
            await self.client.verify_token(token)

    async def test_cors_preflight_for_spa(self):
        app = create_app(self.config)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as http:
            response = await http.options(
                "/api/v1/auth/me",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.headers["Access-Control-Allow-Origin"], "http://localhost:5173"
            )
            response = await http.options(
                "/api/v1/auth/me",
                headers={
                    "Origin": "https://untrusted.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
            self.assertEqual(response.status_code, 400)

    async def test_http_principal_and_error_contracts(self):
        app = create_app(self.config)
        app.dependency_overrides[get_keycloak_client] = lambda: self.client
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.get("/api/v1/auth/me")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
            for header in ("Basic abc", "Bearer malformed"):
                response = await http.get("/api/v1/auth/me", headers={"Authorization": header})
                self.assertEqual(response.status_code, 401)
            response = await http.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {self.token()}"}
            )
            self.assertEqual(response.json()["type"], "creator")
            response = await http.get(
                "/api/v1/users/me",
                headers={
                    "Authorization": f"Bearer {self.token()}",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["id"], str(self.subject))
            service = self.token(changes={"auth_type": "client", "azp": "tiu-media-hub-worker"})
            headers = {"Authorization": f"Bearer {service}"}
            response = await http.get("/api/v1/auth/me", headers=headers)
            self.assertEqual(response.json()["type"], "client")
            response = await http.get("/api/v1/users/me", headers=headers)
            self.assertEqual(response.status_code, 403)
            response = await http.post(
                "/api/v1/assets", headers=headers, json={"title": "example"}
            )
            self.assertEqual(response.status_code, 403)
            for path, method in (
                ("/api/v1/assets", "POST"),
                (f"/api/v1/assets/{uuid4()}", "GET"),
                (f"/api/v1/assets/{uuid4()}/uploads", "POST"),
                (f"/api/v1/assets/{uuid4()}/uploads/{uuid4()}/complete", "POST"),
            ):
                response = await http.request(method, path, json={"title": "example"})
                self.assertEqual(response.status_code, 401)

    async def test_http_503_has_no_authentication_challenge(self):
        self.jwks_status = 503
        app = create_app(self.config)
        app.dependency_overrides[get_keycloak_client] = lambda: self.client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http:
            response = await http.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {self.token()}"}
            )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("WWW-Authenticate", response.headers)

    def test_discriminated_schema_and_disjoint_clients(self):
        schema = TypeAdapter(Auth).json_schema()
        self.assertEqual(schema["discriminator"]["propertyName"], "type")
        with self.assertRaises(ValidationError):
            KeycloakConfig(user_client_ids={"same"}, service_client_ids={"same"})
