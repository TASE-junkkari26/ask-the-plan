"""Large proof compression preserves origin's immediate NDJSON handoffs."""
import unittest

import httpx
from fastapi import FastAPI
from starlette.responses import JSONResponse, StreamingResponse

from image_api.app import _EvidenceCompression


class ResponseCompressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_json_compresses_and_streams_remain_unbuffered(self):
        app = FastAPI()
        app.add_middleware(_EvidenceCompression, minimum_size=64 * 1024, compresslevel=3)
        proof = {"source_evidence": "native-source-record " * 10000}

        @app.get("/proof")
        async def json_proof():
            return JSONResponse(proof)

        @app.get("/stream")
        async def stream():
            return StreamingResponse(iter(['{"type":"handoff"}\n', '{"type":"result"}\n']),
                                     media_type="application/x-ndjson")

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.get("/proof", headers={"Accept-Encoding": "gzip"})
            self.assertEqual(response.headers.get("content-encoding"), "gzip")
            self.assertEqual(response.json(), proof)
            response = await client.get("/stream", headers={"Accept": "application/x-ndjson", "Accept-Encoding": "gzip"})
            self.assertNotIn("content-encoding", response.headers)
            self.assertEqual(response.text.splitlines(), ['{"type":"handoff"}', '{"type":"result"}'])
