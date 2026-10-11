import asyncio
import secrets
import time
import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestServer
from pydantic import BaseModel, ValidationError

from src.core.services.base import SrvBaseClient, SrvBaseConfig
from src.core.services.base.exceptions import OAuthError, ServiceResponseError


class Result(BaseModel):
    ok: bool


class ServiceClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token_calls = 0
        self.api_calls = 0
        self.expires_in = 300
        self.token_status = 200
        self.token_override = None
        self.api_status = 200
        self.reject_first_token = False
        self.forms = []
        self.auth_headers = []
        self.secret = secrets.token_urlsafe(24)
        app = web.Application()
        app.router.add_post("/token", self.issue_token)
        app.router.add_route("*", "/api/resource", self.resource)
        self.server = TestServer(app)
        await self.server.start_server()
        self.addAsyncCleanup(self.server.close)
        self.config = SrvBaseConfig(
            base_url=str(self.server.make_url("/api/")),
            token_url=str(self.server.make_url("/token")),
            client_id="worker",
            client_secret=self.secret,
            scope="dam",
        )
        self.client = SrvBaseClient(self.config)
        self.addAsyncCleanup(self.client.close)

    async def issue_token(self, request):
        self.token_calls += 1
        self.forms.append(dict(await request.post()))
        self.assertNotIn("Authorization", request.headers)
        await asyncio.sleep(0)
        data = (
            self.token_override
            if self.token_override is not None
            else {
                "access_token": f"token-{self.token_calls}",
                "expires_in": self.expires_in,
                "token_type": "Bearer",
            }
        )
        return web.json_response(data, status=self.token_status)

    async def resource(self, request):
        self.api_calls += 1
        authorization = request.headers.get("Authorization")
        self.auth_headers.append(authorization)
        await asyncio.sleep(0)
        response_status = (
            401
            if self.reject_first_token and authorization == "Bearer token-1"
            else self.api_status
        )
        return web.json_response({"ok": True}, status=response_status)

    async def fetch(self, method="GET", path="resource"):
        return await self.client.request_json(method, path, Result)

    async def test_first_request_and_concurrent_token_cache(self):
        results = await asyncio.gather(*(self.fetch() for _ in range(20)))
        self.assertTrue(all(result.ok for result in results))
        self.assertEqual(self.token_calls, 1)
        self.assertEqual(
            self.forms,
            [
                {
                    "grant_type": "client_credentials",
                    "client_id": "worker",
                    "client_secret": self.secret,
                    "scope": "dam",
                }
            ],
        )
        self.assertEqual(set(self.auth_headers), {"Bearer token-1"})
        self.assertNotIn(self.secret, repr(self.config))

    async def test_expiry_uses_expires_in_and_refresh_margin(self):
        await self.fetch()
        with patch("src.core.services.base.client.monotonic", return_value=time.monotonic() + 271):
            await asyncio.gather(*(self.fetch() for _ in range(20)))
        self.assertEqual(self.token_calls, 2)

    async def test_short_lived_tokens_are_cached(self):
        self.expires_in = 10
        await self.fetch()
        await self.fetch()
        self.assertEqual(self.token_calls, 1)

    async def test_concurrent_401_refreshes_once(self):
        self.reject_first_token = True
        await asyncio.gather(*(self.fetch() for _ in range(20)))
        self.assertEqual(self.token_calls, 2)
        self.assertIn("Bearer token-2", self.auth_headers)

    async def test_permanent_401_is_retried_only_once(self):
        self.api_status = 401
        with self.assertRaises(ServiceResponseError) as raised:
            await self.fetch()
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(self.api_calls, 2)
        self.assertEqual(self.token_calls, 2)

    async def test_post_is_not_replayed(self):
        self.api_status = 401
        with self.assertRaises(ServiceResponseError):
            await self.fetch("POST")
        self.assertEqual(self.api_calls, 1)
        self.assertEqual(self.token_calls, 1)

    async def test_other_errors_and_redirects_are_not_retried(self):
        for response_status in (302, 403, 500):
            self.api_status = response_status
            before = self.api_calls
            with self.assertRaises(ServiceResponseError) as raised:
                await self.fetch()
            self.assertEqual(raised.exception.status_code, response_status)
            self.assertEqual(self.api_calls, before + 1)

    async def test_rejected_credentials_are_not_exposed(self):
        self.token_status = 401
        self.token_override = {"error": "invalid_client", "error_description": "test-secret"}
        with self.assertRaises(OAuthError) as raised:
            await self.fetch()
        self.assertNotIn("test-secret", str(raised.exception))
        self.assertEqual(self.api_calls, 0)

    async def test_invalid_token_response(self):
        for token in (
            {},
            {"access_token": "", "expires_in": 10, "token_type": "Bearer"},
            {"access_token": "token", "expires_in": 0, "token_type": "Bearer"},
            {"access_token": "token", "expires_in": 10, "token_type": "MAC"},
        ):
            self.token_override = token
            with self.subTest(token=token), self.assertRaises(OAuthError):
                await self.fetch()
        self.assertEqual(self.api_calls, 0)

    async def test_external_urls_and_path_escape_rejected_before_token_fetch(self):
        for path in (
            "https://attacker.example/",
            "//attacker.example/",
            "../outside",
            "resource#fragment",
            "\\\\attacker.example",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                await self.fetch(path=path)
        self.assertEqual(self.token_calls, 0)

    async def test_close_clears_token_and_releases_session(self):
        await self.fetch()
        await self.client.close()
        await self.client.close()
        await self.fetch()
        self.assertEqual(self.token_calls, 2)

    def test_invalid_configuration(self):
        for values in (
            {"timeout": 0},
            {"pool_limit": 0},
            {"base_url": "https://user:secret@example.com/"},
        ):
            with self.assertRaises(ValidationError):
                SrvBaseConfig.model_validate({**self.config.model_dump(), **values})
