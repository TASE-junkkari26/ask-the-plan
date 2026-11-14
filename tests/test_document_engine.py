"""Credential-free native document invariants with registered synthetic PDFs."""
from __future__ import annotations

import asyncio
from decimal import Decimal
import hashlib
from io import BytesIO
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from contracts import models as m
from contracts.validation import validate_answer
from document_engine import DocumentError, DocumentStore, extract_pdf
from document_engine.geometry import GeometryCalibration, SourcePolygon, calibrated_area
from document_engine.quantities import calculate, parse_quantity
from document_engine.tables import extract_table


def source_pdf(items=None, *, rotate=0, crop=None, page_size=(300, 120)):
    """A valid vector PDF, without a PDF-writing test dependency."""
    items = items or [(10, 100, "Type"), (100, 100, "QTY"), (180, 100, "Units"),
                      (10, 75, "121.A"), (100, 75, "2"), (180, 75, "3"),
                      (10, 50, "7.16"), (100, 50, "4"), (180, 50, "2")]
    stream = "\n".join(f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET" for x, y, text in items).encode("ascii")
    extra = f" /Rotate {rotate}" + (f" /CropBox [{' '.join(map(str, crop))}]" if crop else "")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_size[0]} {page_size[1]}]" + extra + " /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>").encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    raw, offsets = b"%PDF-1.4\n", []
    for index, item in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += f"{index} 0 obj\n".encode() + item + b"\nendobj\n"
    position = len(raw)
    raw += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    raw += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    raw += f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{position}\n%%EOF\n".encode()
    return raw


def display(width=600, height=240):
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, "PNG")
    return output.getvalue()


def snapshot(**changes):
    return {"page_index": 0, "rotation": 0, "viewport_transform": [2, 0, 0, -2, 0, 240],
            "source_bounds": [0, 0, 300, 120], **changes}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = DocumentStore(Path(self.temporary.name), max_sessions=1)
        self.addCleanup(self.store.close)

    def test_distinct_original_display_hashes_immutable_snapshot_and_no_paths(self):
        data, png = source_pdf(), display()
        context = snapshot()
        session = self.store.register(data, r"C:\drawings\121.A.pdf", png, context)
        context["page_index"] = 1
        self.assertEqual(session.source_sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(session.display_sha256, hashlib.sha256(png).hexdigest())
        self.assertEqual(session.snapshot["page_index"], 0)
        self.assertEqual(session.filename, "121.A.pdf")
        self.assertNotIn("original_path", session.public())
        with self.assertRaises(TypeError):
            session.snapshot["page_index"] = 2
        with self.assertRaises(TypeError):
            session.snapshot["viewport_transform"][0] = 3

    def test_hash_dimension_and_singular_transform_mismatches_rejected(self):
        for kwargs, context, code in [({"source_sha256": "0" * 64}, snapshot(), "source_hash_mismatch"),
                                     ({"display_sha256": "0" * 64}, snapshot(), "display_hash_mismatch"),
                                     ({}, snapshot(display_width=40), "snapshot_mismatch"),
                                     ({}, snapshot(viewport_transform=[0, 0, 0, 0, 0, 0]), "invalid_snapshot")]:
            with self.subTest(code=code), self.assertRaises(DocumentError) as caught:
                self.store.register(source_pdf(), "file.pdf", display(), context, **kwargs)
            self.assertEqual(caught.exception.code, code)

    def test_active_lease_survives_delete_and_prevents_eviction(self):
        session = self.store.register(source_pdf(), "file.pdf", display(), snapshot())
        with self.store.lease(session.source_id):
            with self.assertRaises(DocumentError) as caught:
                self.store.register(source_pdf(), "other.pdf", display(), snapshot())
            self.assertEqual(caught.exception.code, "source_store_busy")
            self.store.delete(session.source_id)
            self.assertTrue(session.original_path.exists())
            with self.assertRaises(DocumentError):
                self.store.get(session.source_id)
        self.assertFalse(session.original_path.exists())

    def test_lru_and_expired_source_does_not_reuse_ids(self):
        first = self.store.register(source_pdf(), "first.pdf", display(), snapshot())
        second = self.store.register(source_pdf(), "second.pdf", display(), snapshot())
        self.assertNotEqual(first.source_id, second.source_id)
        self.assertFalse(first.original_path.exists())
        self.store._entries[second.source_id].touched -= self.store.ttl_seconds + 1
        with self.assertRaises(DocumentError) as caught:
            self.store.get(second.source_id)
        self.assertEqual(caught.exception.code, "missing_source")


@unittest.skipUnless(shutil.which("node") and Path("frontend/node_modules/pdfjs-dist").is_dir(), "Node and locked frontend PDF.js dependencies required")
class NativePdfTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = DocumentStore(Path(self.temporary.name))
        self.addCleanup(self.store.close)

    async def test_actual_worker_native_spans_table_rows_multiply_and_sum(self):
        session = self.store.register(source_pdf(), "schedule.pdf", display(), snapshot())
        with self.store.lease(session.source_id):
            page = await extract_pdf(session)
        self.assertTrue(page.mapping_verified)
        self.assertTrue(page.text_enumeration_complete)
        by_text = {span.text: span for span in page.spans}
        self.assertEqual(page.lookup("121.A")[0].text, "121.A")
        self.assertEqual(by_text["121.A"].native_transform[4:], (10, 75))
        headers = {key: [by_text[key].id] for key in ("Type", "QTY", "Units")}
        table = extract_table(page, headers, bbox=(0, 20, 600, 200), units={"QTY": "1", "Units": "1"})
        self.assertTrue(table.enumeration_complete)
        self.assertEqual(len(table.rows), 2)
        self.assertEqual(table.rows[0].cells["Type"].text, "121.A")
        result, rows = table.aggregate("sum", "QTY", multiplier_column="Units")
        self.assertEqual(result.result.magnitude, Decimal(14))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].result.magnitude, Decimal(6))
        self.assertIn(by_text["QTY"].id, result.result.anchor_ids)

    async def test_rotated_cropped_page_mapping_and_stale_transform_rejection(self):
        session = self.store.register(source_pdf(rotate=90, crop=(10, 20, 290, 110)), "crop.pdf", display(180, 560),
            snapshot(rotation=90, source_bounds=[10, 20, 290, 110], viewport_transform=[0, 2, 2, 0, -40, -20]))
        page = await extract_pdf(session)
        self.assertTrue(page.mapping_verified)
        self.assertEqual(page.source_bounds, (10, 20, 290, 110))
        wrong = self.store.register(source_pdf(), "wrong.pdf", display(), snapshot(viewport_transform=[2, 0, 0, -2, 1, 240]))
        with self.assertRaises(DocumentError) as caught:
            await extract_pdf(wrong)
        self.assertEqual(caught.exception.code, "mapping_mismatch")

    async def test_no_transform_retains_native_only_anchors_not_guessed_mapping(self):
        session = self.store.register(source_pdf(), "source.pdf", display(), {"page_index": 0})
        page = await extract_pdf(session)
        self.assertFalse(page.mapping_verified)
        self.assertIsNone(page.spans[0].display_bbox)

    async def test_more_than_one_hundred_source_rows_are_materialized_without_truncation(self):
        items = [(10, 4950, "Type"), (100, 4950, "QTY")]
        for index in range(205):
            items.extend([(10, 4900 - 20 * index, f"D-{index}"), (100, 4900 - 20 * index, "1")])
        session = self.store.register(source_pdf(items, page_size=(300, 5000)), "large.pdf", display(600, 10000),
            snapshot(source_bounds=[0, 0, 300, 5000], viewport_transform=[2, 0, 0, -2, 0, 10000]))
        page = await extract_pdf(session)
        table = extract_table(page, {key: [page.lookup(key)[0].id] for key in ("Type", "QTY")},
                              bbox=(0, 20, 600, 10000), units={"QTY": "1"})
        self.assertEqual(len(table.rows), 205)
        total, _ = table.aggregate("sum", "QTY")
        self.assertEqual(total.result.magnitude, Decimal(205))

    async def test_repeated_native_headers_and_unresolved_cross_column_text(self):
        items = [(10, 100, "Type"), (100, 100, "QTY"), (10, 75, "121.A"), (100, 75, "2"),
                 (10, 50, "Type"), (100, 50, "QTY"), (10, 25, "7.16"), (100, 25, "4")]
        session = self.store.register(source_pdf(items), "repeat.pdf", display(), snapshot())
        page = await extract_pdf(session)
        table = extract_table(page, {key: [page.lookup(key)[0].id] for key in ("Type", "QTY")}, bbox=(0, 20, 600, 240), units={"QTY": "1"})
        self.assertEqual(len(table.rows), 2)
        self.assertTrue(any("repeated" in warning for warning in table.warnings))
        bad_items = [(10, 100, "Type"), (100, 100, "QTY"), (10, 75, "A merged row crossing both columns"), (100, 75, "2")]
        bad_session = self.store.register(source_pdf(bad_items), "merged.pdf", display(), snapshot())
        bad_page = await extract_pdf(bad_session)
        bad_table = extract_table(bad_page, {key: [bad_page.lookup(key)[0].id] for key in ("Type", "QTY")}, bbox=(0, 20, 600, 240), units={"QTY": "1"})
        self.assertFalse(bad_table.enumeration_complete)
        with self.assertRaises(DocumentError) as caught:
            bad_table.aggregate("sum", "QTY")
        self.assertEqual(caught.exception.code, "incomplete_table")

    async def test_repeated_identifier_not_silently_chosen(self):
        from answer_api.native import answer_native
        from answer_api.budget import AnswerBudget
        session = self.store.register(source_pdf([(10, 100, "121.A"), (10, 75, "121.A")]), "repeat.pdf", display(), snapshot())
        source = m.AnswerSourceBinding(**session.public()["snapshot"], source_id=session.source_id, kind="pdf", scope_label="Selected PDF page")
        result, context = await answer_native(session, m.AnswerRequestedPart(key="find", question='Find "121.A"'), source, "req", AnswerBudget(), None, "en")
        self.assertEqual(result.status, "needs_clarification")
        self.assertIsNone(context)

    async def test_native_lookup_and_qualified_schedule_create_semantically_valid_answer(self):
        from answer_api.native import _execute, NativeProposal, answer_native
        from answer_api.budget import AnswerBudget
        from answer_api.realize import realize_answer
        session = self.store.register(source_pdf(), "schedule.pdf", display(), snapshot())
        source = m.AnswerSourceBinding(**session.public()["snapshot"], source_id=session.source_id, kind="pdf", scope_label="Selected PDF page")
        part = m.AnswerRequestedPart(key="find", question='Find "121.A"')
        answer_part, context = await answer_native(session, part, source, "req", AnswerBudget(), None, "en")
        self.assertEqual(answer_part.status, "answered")
        self.assertEqual(answer_part.result.claims[0].value.rows[0]["native:source_text"].value.text, "121.A")
        page = await extract_pdf(session)
        by_text = {span.text: span for span in page.spans}
        schedule = m.AnswerRequestedPart(key="total", question="Sum QTY times Units in the schedule")
        proposal = NativeProposal(operation="sum", headers={key: [by_text[key].id] for key in ("Type", "QTY", "Units")},
                                  last_row_span_ids=[by_text["7.16"].id], value_column="QTY", multiplier_column="Units", units={"QTY": "1", "Units": "1"})
        schedule_part, schedule_context = _execute(page, proposal, schedule, source, "req", "en")
        self.assertEqual(schedule_part.status, "partial")
        self.assertEqual(schedule_part.result.claims[0].value.magnitude, "14")
        self.assertEqual(schedule_context.bundle.coverage[0].completeness, "unknown")
        question = "Find 121.A and calculate the selected schedule rows"
        response = m.AnswerResponse(request_id="req", question=question, question_sha256=hashlib.sha256(question.encode()).hexdigest(), source=source,
            interpretation=m.AnswerIntent(scope_label=source.scope_label, requested_parts=[part, schedule]), parts=[answer_part, schedule_part],
            evidence_contexts=[context, schedule_context], metrics=m.AnswerMetrics(elapsed_ms=0))
        response.narrative = realize_answer(response)
        validate_answer(response)

    async def test_missing_filter_cells_remain_unresolved_and_missing_notes_are_not_facts(self):
        from answer_api.native import _execute, NativeProposal, NativeFilter
        items = [(10, 100, 'Type'), (100, 100, 'QTY'), (180, 100, 'Notes'),
                 (10, 75, '121.A'), (100, 75, '2'), (100, 50, '4'), (180, 50, 'Recorded')]
        session = self.store.register(source_pdf(items), 'missing.pdf', display(), snapshot())
        source = m.AnswerSourceBinding(**session.public()['snapshot'], source_id=session.source_id,
                                       kind='pdf', scope_label='Selected PDF page')
        page = await extract_pdf(session)
        spans = {span.text: span for span in page.spans}
        proposal = NativeProposal(operation='sum', headers={key: [spans[key].id] for key in ('Type', 'QTY', 'Notes')},
            last_row_span_ids=[spans['4'].id], value_column='QTY', units={'QTY': '1'},
            filters=[NativeFilter(column='Type', literal='121.A')])
        part, context = _execute(page, proposal, m.AnswerRequestedPart(key='sum', question='Sum QTY for 121.A'), source, 'req', 'en')
        self.assertEqual(part.result.claims[0].value.magnitude, '2')
        self.assertEqual([item.count for item in part.result.entity_sets], [1, 0, 1])
        missing = [fact for fact in context.bundle.facts if fact.status == 'not_extracted']
        self.assertEqual(len(missing), 2)
        self.assertTrue(all(fact.value is None for fact in missing))
        final = part.result.calculations[-1]
        self.assertFalse({fact.id for fact in missing} & set(final.fact_ids))
        self.assertEqual(len(context.bundle.coverage[0].unresolved_entity_ids), 1)

    async def test_timeout_and_cancellation_wait_for_owned_worker_before_lease_cleanup(self):
        session = self.store.register(source_pdf(), "source.pdf", display(), snapshot())
        actual_spawn = asyncio.create_subprocess_exec
        processes = []

        async def slow_worker(*args, **kwargs):
            process = await actual_spawn(sys.executable, "-c", "import time;time.sleep(30)", **kwargs)
            processes.append(process)
            return process

        with patch("document_engine.pdf.asyncio.create_subprocess_exec", side_effect=slow_worker):
            with self.store.lease(session.source_id):
                with self.assertRaises(DocumentError) as caught:
                    await extract_pdf(session, timeout_seconds=.03, use_cache=False)
                self.assertEqual(caught.exception.code, "native_extraction_timeout")
                self.assertIsNotNone(processes[-1].returncode)
                task = asyncio.create_task(extract_pdf(session, use_cache=False))
                while len(processes) < 2:
                    await asyncio.sleep(.001)
                self.store.delete(session.source_id)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertIsNotNone(processes[-1].returncode)
                self.assertTrue(session.original_path.exists())
            self.assertFalse(session.original_path.exists())


class QuantityTests(unittest.TestCase):
    def quantity(self, text, unit=None):
        return parse_quantity(text, default_unit=unit, anchor_ids=["source:cell"])

    def test_imperial_fraction_decimal_arithmetic_and_unit_basis(self):
        self.assertEqual(self.quantity('5\'-10 3/8"').magnitude, Decimal("70.375"))
        self.assertEqual(self.quantity("21", "1").magnitude, Decimal(21))
        total = calculate("sum", [self.quantity("0.1 m2"), self.quantity("0.2 m2")])
        self.assertEqual(total.result.magnitude, Decimal("0.3"))
        self.assertEqual(self.quantity("2 1/3 ft").quality, "estimated")

    def test_ambiguous_missing_incompatible_and_zero_are_distinct(self):
        for text, unit, code in [("12", None, "missing_unit"), ("1,234 m2", None, "ambiguous_number"), ("N/A", "m2", "unparsed_quantity")]:
            with self.subTest(text=text), self.assertRaises(DocumentError) as caught:
                self.quantity(text, unit)
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.quantity("0 m2").magnitude, Decimal(0))
        with self.assertRaises(DocumentError) as caught:
            calculate("divide", [self.quantity("10 m2"), self.quantity("0 m2")])
        self.assertEqual(caught.exception.code, "division_by_zero")
        with self.assertRaises(DocumentError) as caught:
            calculate("sum", [self.quantity("2 m2"), self.quantity("3 m")])
        self.assertEqual(caught.exception.code, "incompatible_dimensions")


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.calibration = GeometryCalibration("revision", "view", Decimal("1"), ("native:units",), "native_units")
        self.shell = ((0., 0.), (10., 0.), (10., 10.), (0., 10.), (0., 0.))

    def test_shell_minus_column_holes_and_union_not_bounding_box(self):
        hole = ((2., 2.), (4., 2.), (4., 4.), (2., 4.), (2., 2.))
        source = SourcePolygon("room", "revision", "view", self.shell, (hole,), ("source:room",))
        result = calibrated_area([source], calibration=self.calibration)
        self.assertEqual(result.result.magnitude, Decimal(96))
        self.assertEqual(result.result.quality, "estimated")
        self.assertIn("native:units", result.result.anchor_ids)

    def test_cross_revision_calibration_invalid_holes_and_overlap_rejected(self):
        source = SourcePolygon("room", "revision", "view", self.shell, (), ("source:room",))
        other = SourcePolygon("other", "other_revision", "view", self.shell, (), ("source:other",))
        with self.assertRaises(DocumentError) as caught:
            calibrated_area([other], calibration=self.calibration)
        self.assertEqual(caught.exception.code, "calibration_scope_mismatch")
        duplicate = SourcePolygon("overlap", "revision", "view", self.shell, (), ("source:overlap",))
        with self.assertRaises(DocumentError) as caught:
            calibrated_area([source, duplicate], calibration=self.calibration)
        self.assertEqual(caught.exception.code, "overlapping_geometry")


if __name__ == "__main__":
    unittest.main()
