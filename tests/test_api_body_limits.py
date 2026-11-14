"""Keep large IFC uploads from relaxing image/question request limits."""
from __future__ import annotations

import unittest

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse

from image_api.app import BodyLimitMiddleware


class ApiBodyLimitTests(unittest.IsolatedAsyncioTestCase):
    async def post(self, path, *, streaming=False, size=30):
        async def consume(scope, receive, send):
            body = await Request(scope, receive).body()
            await JSONResponse({"bytes": len(body)})(scope, receive, send)

        app = BodyLimitMiddleware(consume, max_bytes=20, ifc_max_bytes=40)

        async def chunks():
            yield b"a" * (size // 2)
            yield b"b" * (size - size // 2)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                     base_url="http://test") as client:
            return await client.post(path, content=chunks() if streaming else b"x" * size)

    async def test_ifc_upload_uses_its_own_larger_cap(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                response = await self.post("/api/ifc/models", streaming=streaming)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), {"bytes": 30})
                self.assertEqual(response.headers["cache-control"], "no-store")

    async def test_images_and_questions_retain_the_smaller_cap(self):
        for path in ("/api/v1/candidates", "/api/ifc/questions"):
            for streaming in (False, True):
                with self.subTest(path=path, streaming=streaming):
                    response = await self.post(path, streaming=streaming)
                    self.assertEqual(response.status_code, 413, response.text)
                    self.assertEqual(response.json()["code"], "request_too_large")
                    self.assertEqual(response.json()["request_id"], response.headers["x-request-id"])

    async def test_ifc_cap_is_enforced_without_content_length(self):
        response = await self.post("/api/ifc/models", streaming=True, size=41)
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(response.json()["code"], "request_too_large")


if __name__ == "__main__":
    unittest.main()
