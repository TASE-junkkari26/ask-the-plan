"""Synthetic DXF rendering and local HTTP integration; no inference calls."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch
import xml.etree.ElementTree as ET

import ezdxf
import httpx
from pydantic import ValidationError

from contracts.models import DxfPreviewResponse
from dxf_api.render import PreviewError, render_dxf
from dxf_api.routes import render_in_process
from ifc_api.config import IfcSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.errors import ApiError
from nemotron import ConfigurationError


def drawing():
    doc = ezdxf.new("R2010")
    doc.units = 6
    model = doc.modelspace()
    model.add_lwpolyline([(0, 0), (20, 0), (20, 10), (0, 10)], close=True)
    model.add_text("121.A Keittiö", dxfattribs={"insert": (2, 3), "height": 1})
    block = doc.blocks.new("Ovi 7.16")
    block.add_arc((0, 0), radius=1, start_angle=0, end_angle=90)
    block.add_line((0, 0), (1, 0))
    model.add_blockref("Ovi 7.16", (5, 0), dxfattribs={"rotation": 90, "xscale": 2})
    paper = doc.layouts.new("Piirustus 7.16")
    paper.add_circle((5, 5), radius=2)
    return doc


class DxfRenderTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="ask-plan-dxf-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "source.dxf"

    def save(self, doc=None, *, binary=False):
        (doc or drawing()).saveas(self.path, fmt="bin" if binary else "asc")
        return self.path

    def test_selected_layout_has_bounded_self_contained_svg_and_original_hash(self):
        self.save()
        original = self.path.read_bytes()
        model = render_dxf(self.path)
        paper = render_dxf(self.path, 2)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(model.source_sha256, hashlib.sha256(original).hexdigest())
        self.assertEqual(model.layouts, ["Model", "Piirustus 7.16"])
        self.assertEqual(paper.layouts[paper.page - 1], "Piirustus 7.16")
        self.assertEqual(model.insunits, 6)
        self.assertNotEqual(model.svg, paper.svg)
        self.assertEqual(model.status, "rendered")
        self.assertEqual(model.warnings, [])
        for preview in (model, paper):
            self.assertLessEqual(preview.width * preview.height, 8_000_000)
            self.assertLessEqual(max(preview.width, preview.height), 4096)
            root = ET.fromstring(preview.svg)
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
            self.assertEqual(root.get("width"), str(preview.width))
            self.assertEqual(root.get("height"), str(preview.height))
            self.assertGreater(len(list(root.iter())), 3)
            self.assertNotIn("<script", preview.svg)
            self.assertNotIn("href=", preview.svg)
            self.assertNotIn(self.directory.name, preview.svg)

    def test_binary_dxf_and_legacy_encoding_keep_layout_names(self):
        self.save(binary=True)
        self.assertEqual(render_dxf(self.path).layouts[1], "Piirustus 7.16")
        doc = ezdxf.new("R2000")
        doc.layouts.new("Pohja Ääni 121.A").add_text("Keittiö 7.16")
        self.save(doc)
        result = render_dxf(self.path)
        self.assertEqual(result.layouts, ["Pohja Ääni 121.A"])
        self.assertEqual(result.status, "rendered")

    def test_hidden_layers_do_not_expand_the_view_or_become_omission_warnings(self):
        doc = drawing()
        self.save(doc)
        baseline = render_dxf(self.path)
        doc.layers.new("Piilotettu", dxfattribs={"flags": 1})
        doc.modelspace().add_line((1e6, 1e6), (2e6, 2e6), dxfattribs={"layer": "Piilotettu"})
        self.save(doc)
        result = render_dxf(self.path)
        self.assertEqual(result.svg, baseline.svg)
        self.assertEqual(result.status, "rendered")
        self.assertEqual(result.warnings, [])

    def test_external_references_images_and_unsupported_entities_are_disclosed(self):
        doc = drawing()
        doc.add_xref_def("/private/source-never-opened.dxf", "external")
        xref = doc.modelspace().add_blockref("external", (0, 0))
        image = doc.add_image_def("/private/image-never-opened.png", (20, 20))
        doc.modelspace().add_image(image, (0, 0), (1, 1))
        solid = doc.modelspace().add_3dsolid()
        # Empty solids are omitted by the DXF writer itself. Keep SAT content so
        # this fixture actually contains an unsupported entity after reloading.
        solid.sat = ["700 0 1 0 ", "Synthetic fixture", "1 1e-6 1e-10",
                     "body $-1 -1 $-1 $-1 $-1 $-1 #"]
        self.save(doc)
        result = render_dxf(self.path)
        self.assertEqual(result.status, "partial")
        text = " ".join(result.warnings)
        for kind in ("INSERT", "IMAGE", "3DSOLID"):
            self.assertIn(kind, text)
        self.assertIn(xref.dxf.handle, text)
        self.assertNotIn("/private/", text + result.svg)

    def test_empty_hidden_corrupt_and_nonexistent_layouts_are_explicit_errors(self):
        self.path.write_bytes(b"This is not DXF")
        with self.assertRaisesRegex(PreviewError, "damaged or unsupported"):
            render_dxf(self.path)
        self.save(ezdxf.new())
        with self.assertRaisesRegex(PreviewError, "no drawing entities"):
            render_dxf(self.path)
        doc = ezdxf.new()
        doc.layers.new("hidden", dxfattribs={"flags": 1})
        doc.modelspace().add_line((0, 0), (1, 1), dxfattribs={"layer": "hidden"})
        self.save(doc)
        with self.assertRaisesRegex(PreviewError, "no renderable visible geometry"):
            render_dxf(self.path)
        self.save()
        with self.assertRaisesRegex(PreviewError, "available DXF layout"):
            render_dxf(self.path, 3)

    def test_unknown_units_stay_unknown_and_complexity_budgets_reject(self):
        doc = drawing()
        del doc.header["$INSUNITS"]
        self.save(doc)
        self.assertIsNone(render_dxf(self.path).insunits)
        with patch("dxf_api.render.MAX_ENTITIES", 1):
            with self.assertRaisesRegex(PreviewError, "entity limit"):
                render_dxf(self.path)
        with patch("dxf_api.render.MAX_SVG_BYTES", 20):
            with self.assertRaisesRegex(PreviewError, "too complex"):
                render_dxf(self.path)

    def test_contract_rejects_unbound_layout_and_unexplained_partial(self):
        self.save()
        value = render_dxf(self.path).model_dump()
        for changes in ({"page": 3}, {"status": "partial", "warnings": []},
                        {"width": 4096, "height": 4096}, {"layouts": ["Model", "Model"]}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                DxfPreviewResponse.model_validate({**value, **changes})


class DxfHttpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="ask-plan-dxf-http-test-")
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name) / "source.dxf"
        drawing().saveas(path)
        self.content = path.read_bytes()

    @asynccontextmanager
    async def api(self):
        def unconfigured_client():
            raise ConfigurationError("Synthetic test: no inference credentials.")

        app = create_app(settings=ApiSettings(), ifc_settings=IfcSettings(),
                         client_factory=unconfigured_client)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                yield client

    async def post(self, client, *, content=None, page="1"):
        return await client.post("/api/dxf/preview", data={"page": page}, files={
            "file": ("pohja.121.A.DXF", self.content if content is None else content, "application/octet-stream"),
        })

    async def test_real_worker_http_preview_needs_no_model_or_credentials_and_cleans_up(self):
        paths = []
        original = render_in_process

        async def tracked(source, page):
            paths.append(source.parent)
            return await original(source, page)

        with patch("dxf_api.routes.render_in_process", side_effect=tracked):
            async with self.api() as client:
                response = await self.post(client, page="2")
        self.assertEqual(response.status_code, 200, response.text)
        preview = DxfPreviewResponse.model_validate(response.json())
        self.assertEqual(preview.layouts[preview.page - 1], "Piirustus 7.16")
        self.assertEqual(preview.source_sha256, hashlib.sha256(self.content).hexdigest())
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("/tmp/", response.text)
        self.assertNotIn("answer", response.json())
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() for path in paths))

    async def test_bad_form_empty_invalid_file_and_unavailable_layout_have_safe_errors(self):
        async with self.api() as client:
            responses = [await client.post("/api/dxf/preview", json={"file": "source"}),
                         await self.post(client, content=b""),
                         await self.post(client, content=b"not a DXF"),
                         await self.post(client, page="3"),
                         await self.post(client, page="0"),
                         await client.post("/api/dxf/preview", data={"page": "1", "extra": "x"},
                                           files={"file": ("source.dxf", self.content)})]
        self.assertEqual([r.status_code for r in responses], [415, 422, 422, 422, 422, 422])
        for response in responses:
            self.assertEqual(response.json()["request_id"], response.headers["x-request-id"])
            self.assertNotIn("/tmp/", response.text)

    async def test_file_size_is_bounded_before_rendering(self):
        renderer = AsyncMock()
        with patch("dxf_api.routes.MAX_DXF_BYTES", 10), patch("dxf_api.routes.render_in_process", renderer):
            async with self.api() as client:
                response = await self.post(client)
        self.assertEqual(response.status_code, 413)
        renderer.assert_not_called()

    async def test_timeout_cancels_renderer_and_removes_request_files(self):
        paths = []
        cancelled = []

        async def slow(source, page):
            paths.append(source.parent)
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        with patch("dxf_api.routes.DEADLINE_SECONDS", 0.05), patch("dxf_api.routes.render_in_process", side_effect=slow):
            async with self.api() as client:
                response = await self.post(client)
        self.assertEqual(response.status_code, 504, response.text)
        self.assertTrue(cancelled)
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() for path in paths))

    async def test_disconnect_cancels_renderer_before_removing_source(self):
        started = asyncio.Event()
        paths = []
        retained_during_cancellation = []

        async def slow(source, page):
            paths.append(source.parent)
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                retained_during_cancellation.append(source.exists())

        async def disconnected(request):
            return started.is_set()

        with patch("dxf_api.routes.render_in_process", side_effect=slow), patch(
                "starlette.requests.Request.is_disconnected", disconnected):
            async with self.api() as client:
                response = await self.post(client)
        self.assertEqual(response.status_code, 499, response.text)
        self.assertEqual(retained_during_cancellation, [True])
        self.assertTrue(all(not path.exists() for path in paths))

    async def test_two_preview_slots_reject_extra_requests_and_recover(self):
        entered = asyncio.Queue()
        release = asyncio.Event()

        async def slow(source, page):
            await entered.put(source)
            await release.wait()
            raise ApiError(422, "synthetic_render_error", "Synthetic preview error.")

        with patch("dxf_api.routes.render_in_process", side_effect=slow):
            async with self.api() as client:
                first = asyncio.create_task(self.post(client))
                second = asyncio.create_task(self.post(client))
                await entered.get()
                await entered.get()
                busy = await self.post(client)
                release.set()
                completed = await asyncio.gather(first, second)
                recovered = await self.post(client)
        self.assertEqual(busy.status_code, 429, busy.text)
        self.assertTrue(busy.json()["retryable"])
        self.assertEqual([r.status_code for r in completed], [422, 422])
        self.assertEqual(recovered.status_code, 422)  # Reached the renderer again.

    async def test_cancelling_process_wait_terminates_owned_worker(self):
        process = AsyncMock()
        process.returncode = None
        waiting = asyncio.Event()

        async def wait():
            if process.returncode is None:
                waiting.set()
                await asyncio.Event().wait()

        def kill():
            process.returncode = -9

        process.wait.side_effect = wait
        process.kill = unittest.mock.Mock(side_effect=kill)
        path = Path(self.directory.name) / "source.dxf"
        with patch("dxf_api.routes.asyncio.create_subprocess_exec", return_value=process):
            task = asyncio.create_task(render_in_process(path, 1))
            await waiting.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
