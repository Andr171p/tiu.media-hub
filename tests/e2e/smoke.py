"""
Сквозная проверка поднятого стека (docker compose up -d --build): реальный вход через Keycloak (PKCE),
загрузка с проверкой SHA-256, фоновая обработка, CDN, права коллекций, версии, сервисный доступ, поиск.

Запуск: uv run python -m tests.e2e.smoke
Создаёт данные в dev-окружении (коллекция «Smoke …»), существующие данные не меняет.
"""

import asyncio
import base64
import hashlib
import io
import os
import secrets
import time
from html.parser import HTMLParser
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import aiohttp
from PIL import Image, ImageDraw

API = os.environ.get("SMOKE_API_URL", "http://localhost:8000/api")
REALM = os.environ.get("SMOKE_REALM_URL", "http://localhost:8081/realms/tiu-media-hub")
WEB_CLIENT = "tiu-media-hub-web"
REDIRECT_URI = "http://localhost:5173/callback"


class _LoginForm(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "form" and dict(attrs).get("id") == "kc-form-login":
            self.action = dict(attrs)["action"]


def check(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  ✓ {message}")


async def login(username: str, password: str) -> str:
    """Authorization Code + PKCE, как это делает SPA."""

    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    query = urlencode(
        {
            "client_id": WEB_CLIENT,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    # Keycloak ставит cookie входа с флагом Secure: localhost по http считаем защищённым, как браузер
    origin = f"{urlsplit(REALM).scheme}://{urlsplit(REALM).netloc}"
    jar = aiohttp.CookieJar(unsafe=True, treat_as_secure_origin=[origin])
    async with aiohttp.ClientSession(cookie_jar=jar) as http:
        async with http.get(f"{REALM}/protocol/openid-connect/auth?{query}") as response:
            form = _LoginForm()
            form.feed(await response.text())
        assert form.action, "Keycloak login form not found"

        async with http.post(
            form.action,
            data={"username": username, "password": password},
            allow_redirects=False,
        ) as response:
            assert response.status == HTTPStatus.FOUND, f"Login failed for {username}: {response.status}"
            code = parse_qs(urlsplit(response.headers["Location"]).query)["code"][0]

        async with http.post(
            f"{REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "client_id": WEB_CLIENT,
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        ) as response:
            response.raise_for_status()
            return (await response.json())["access_token"]


async def service_token() -> str:
    async with aiohttp.ClientSession() as http:
        async with http.post(
            f"{REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "tiu-media-hub-service",
                "client_secret": "dev-service-secret",
            },
        ) as response:
            response.raise_for_status()
            return (await response.json())["access_token"]


class Api:
    def __init__(self, http: aiohttp.ClientSession, token: str) -> None:
        self._http = http
        self._headers = {"Authorization": f"Bearer {token}"}

    async def call(self, method: str, path: str, *, expect: int = 200, **kwargs: Any) -> Any:
        async with self._http.request(method, f"{API}{path}", headers=self._headers, **kwargs) as response:
            body = await response.json() if response.content_type == "application/json" else None
            assert response.status == expect, f"{method} {path}: {response.status} {body}"
            return body


def make_photo(color: str, *, copyright_: str | None = None) -> bytes:
    image = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((500, 200, 1100, 800), fill=color)
    exif = Image.Exif()
    if copyright_:
        exif[0x8298] = copyright_  # Copyright
        exif[0x013B] = "TIU Photographer"  # Artist
    exif[0x8825] = {1: "N", 2: (57.0, 9.0, 0.0)}  # GPSInfo
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90, exif=exif)
    return buffer.getvalue()


async def upload(api: Api, http: aiohttp.ClientSession, data: bytes, filename: str, content_type: str) -> str:
    sha = hashlib.sha256(data).hexdigest()
    upload_ = await api.call(
        "POST",
        "/user/v1/uploads",
        expect=201,
        json={"filename": filename, "contentType": content_type, "sizeBytes": len(data), "sha256": sha},
    )
    target = upload_["target"]
    async with http.put(target["url"], data=data, headers=target["headers"]) as response:
        assert response.status == HTTPStatus.OK, await response.text()
    obj = await api.call("POST", f"/user/v1/uploads/{upload_['id']}/complete")
    return obj["id"]


async def wait_ready(api: Api, asset_id: str, *, version: int, timeout: float = 90) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        asset = await api.call("GET", f"/user/v1/assets/{asset_id}")
        current = asset["currentVersion"]
        if current and current["number"] == version:
            return asset
        if (pending := asset["pendingVersion"]) and pending["status"] == "failed":
            raise AssertionError(f"Processing failed: {pending['error']}")
        await asyncio.sleep(1)
    raise AssertionError("Processing timed out")


async def main() -> None:  # noqa: PLR0915
    ivanov_token, petrova_token = await login("ivanov", "ivanov"), await login("petrova", "petrova")

    async with aiohttp.ClientSession() as http:
        ivanov, petrova = Api(http, ivanov_token), Api(http, petrova_token)

        print("Пользователи")
        me = await ivanov.call("GET", "/user/v1/users/me")
        check(me["displayName"] == "Иван Иванов", "профиль синхронизирован из токена")
        petrova_profile = await petrova.call("GET", "/user/v1/users/me")

        print("Коллекция")
        collection = await ivanov.call(
            "POST",
            "/user/v1/collections",
            expect=201,
            json={"name": f"Smoke {int(time.time())}", "visibility": "private"},
        )
        cid = collection["id"]
        check(collection["role"] == "owner", "создатель — владелец")
        settings = collection["settings"] | {
            "metadataFields": [
                {"key": "event", "label": "Мероприятие", "type": "text", "required": True},
                {"key": "year", "label": "Год", "type": "number"},
            ],
            "license": {"required": True},
            "watermark": {"type": "text", "text": "© ТИУ", "placement": {"x": 0.8, "y": 0.9}},
        }
        await ivanov.call("PUT", f"/user/v1/collections/{cid}/settings", json=settings)
        await petrova.call("GET", f"/user/v1/collections/{cid}", expect=404)
        check(True, "приватная коллекция скрыта от постороннего (404)")

        print("Загрузка и целостность")
        photo = make_photo("red", copyright_="Photo Studio LLC")
        tampered = await ivanov.call(
            "POST",
            "/user/v1/uploads",
            expect=201,
            json={
                "filename": "x.jpg",
                "contentType": "image/jpeg",
                "sizeBytes": len(photo),
                "sha256": hashlib.sha256(b"other").hexdigest(),
            },
        )
        async with http.put(tampered["target"]["url"], data=photo, headers=tampered["target"]["headers"]) as r:
            check(r.status == HTTPStatus.BAD_REQUEST, "хранилище отклоняет файл с чужим SHA-256")

        object_id = await upload(ivanov, http, photo, "red-circle.jpg", "image/jpeg")
        await ivanov.call(
            "POST",
            f"/user/v1/collections/{cid}/assets",
            expect=422,
            json={"objectId": object_id, "originalFilename": "red-circle.jpg", "customMeta": {}},
        )
        check(True, "обязательное поле метаданных проверяется")
        asset = await ivanov.call(
            "POST",
            f"/user/v1/collections/{cid}/assets",
            expect=201,
            json={
                "objectId": object_id,
                "originalFilename": "red-circle.jpg",
                "customMeta": {"event": "День открытых дверей", "year": 2026},
                "tags": ["Кампус", "  кампус "],
            },
        )
        aid = asset["id"]
        check([tag["name"] for tag in asset["tags"]] == ["кампус"], "теги нормализуются")

        print("Обработка")
        asset = await wait_ready(ivanov, aid, version=1)
        current = asset["currentVersion"]
        meta = current["meta"]
        check(meta["kind"] == "image" and meta["width"] == 1600, "метаданные изображения извлечены")
        check(meta["embedded"]["copyright"] == "Photo Studio LLC", "права из EXIF прочитаны")
        codes = {issue["code"] for issue in asset["issues"]}
        check({"license_missing", "embedded_rights_undeclared", "location_embedded"} <= codes, f"замечания: {codes}")
        for kind in ("thumbnail", "preview"):
            async with http.get(current["renditions"][kind]) as r:
                body = await r.read()
                check(r.status == HTTPStatus.OK and body[8:12] == b"WEBP", f"{kind} отдаётся CDN")
                rendition = Image.open(io.BytesIO(body))
                check("exif" not in rendition.info, f"{kind} без EXIF/GPS")

        print("Лицензия")
        asset = await ivanov.call(
            "PATCH",
            f"/user/v1/assets/{aid}",
            json={"license": {"type": "cc-by", "holder": "ТИУ", "validUntil": "2020-01-01"}},
        )
        codes = {issue["code"] for issue in asset["issues"]}
        check({"license_expired", "rights_holder_mismatch"} <= codes, f"просроченная лицензия и чужой правообладатель: {codes}")

        print("Версии")
        rotated = Image.open(io.BytesIO(photo)).rotate(90, expand=True)
        buffer = io.BytesIO()
        rotated.save(buffer, format="JPEG")
        v2_object = await upload(ivanov, http, buffer.getvalue(), "red-circle-edit.jpg", "image/jpeg")
        version = await ivanov.call(
            "POST",
            f"/user/v1/assets/{aid}/versions",
            expect=201,
            json={"objectId": v2_object, "originalFilename": "red-circle-edit.jpg", "sourceVersionId": current["id"]},
        )
        asset = await wait_ready(ivanov, aid, version=2)
        check(asset["currentVersion"]["meta"]["width"] == 1000, "новая версия стала текущей после обработки")
        await ivanov.call("POST", f"/user/v1/assets/{aid}/versions/{current['id']}/promote")
        asset = await ivanov.call("GET", f"/user/v1/assets/{aid}")
        check(asset["currentVersion"]["number"] == 1, "откат к версии 1")
        versions = await ivanov.call("GET", f"/user/v1/assets/{aid}/versions")
        check([item["number"] for item in versions] == [2, 1], "история версий сохранена")
        await ivanov.call(
            "POST",
            f"/user/v1/assets/{aid}/versions",
            expect=409,
            json={"objectId": v2_object, "originalFilename": "dup.jpg"},
        )
        check(version["sourceVersionId"] == current["id"], "версия помнит исходную")

        print("Участники")
        await ivanov.call(
            "POST",
            f"/user/v1/collections/{cid}/members",
            expect=201,
            json={"userId": petrova_profile["id"], "role": "member"},
        )
        visible = await petrova.call("GET", f"/user/v1/collections/{cid}")
        check(visible["role"] == "member", "участник видит коллекцию")
        await petrova.call("PATCH", f"/user/v1/assets/{aid}", expect=403, json={"title": "Чужое"})
        check(True, "участник не редактирует чужой актив")
        download = await petrova.call("GET", f"/user/v1/assets/{aid}/versions/{current['id']}/download")
        async with http.get(download["url"]) as r:
            check(r.status == HTTPStatus.OK and await r.read() == photo, "участник скачивает оригинал байт в байт")

        print("Сервисный доступ")
        service = Api(http, await service_token())
        served = await service.call("GET", f"/client/v1/assets/{aid}")
        check(served["id"] == aid and served["canEdit"] is False, "сервис читает актив через /client")
        await ivanov.call("GET", f"/client/v1/assets/{aid}", expect=403)
        check(True, "пользователь не проходит в /client")

        print("Поиск")
        found: list[str] = []
        for _ in range(60):
            result = await ivanov.call("POST", "/user/v1/search", json={"query": "красный круг"})
            if found := [item["id"] for item in result["items"]]:
                break
            await asyncio.sleep(2)
        check(aid in found, "text-to-image: «красный круг» находит фото")
        result = await petrova.call("POST", "/user/v1/search", json={"query": "кампус", "collectionIds": [cid]})
        check(aid in [item["id"] for item in result["items"]], "участник находит актив по тегу")

    print("\nSmoke OK")


if __name__ == "__main__":
    asyncio.run(main())
