"""Regressions for documentation failures the offline checker must catch."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.check_docs import anchors, check, documents


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def write(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def audit(self, content):
        return check([self.write("README.md", content)], self.root)

    def test_missing_images_and_links_report_source_lines(self):
        report = self.audit("# Guide\n![Image](missing.png)\n[Source](missing.py)\n")
        self.assertEqual(report.checked, 2)
        self.assertEqual(len(report.failures), 2)
        self.assertIn("README.md:2: missing.png", report.failures[0])
        self.assertIn("README.md:3: missing.py", report.failures[1])

    def test_full_collapsed_and_shortcut_references_are_checked_once(self):
        self.write("drawing.png")
        report = self.audit('[Plan][SOURCE File]\n![drawing][]\n[source file]\n\n'
                            '[source file]: drawing.png "Source"\n[drawing]: <drawing.png>\n')
        self.assertEqual(report.checked, 3)
        self.assertEqual(report.failures, [])

    def test_missing_explicit_reference_definition_fails(self):
        report = self.audit("[Drawing][missing reference]\n")
        self.assertEqual(len(report.failures), 1)
        self.assertIn("Missing reference definition", report.failures[0])

    def test_code_and_comments_are_ignored_with_correct_fence_lengths(self):
        report = self.audit('# Real\n````md\n```\n[bad](missing.md)\n```\n````\n'
                            '~~~md\n![bad](missing.png)\n~~~\n'
                            '`[bad](missing.md)` and ``[bad](missing.md) `example` ``\n'
                            '<!-- [bad](missing.md) -->\n[Good](#real)\n')
        self.assertEqual(report.checked, 1)
        self.assertEqual(report.failures, [])

    def test_heading_formatting_setext_html_and_duplicate_slug_collisions(self):
        path = self.write("guide.md", '# Repeat\n# Repeat\n# Repeat-1\n'
                          '## `Types` & [units](units.md)\nSetext title\n===\n'
                          '<a id="manual"></a>\n`<a id="fake"></a>`\n```\n# Hidden\n```\n')
        self.assertEqual(anchors(path), {"repeat", "repeat-1", "repeat-1-1",
                                        "types--units", "setext-title", "manual"})

    def test_encoded_filenames_titles_queries_and_parentheses(self):
        self.write("guide #1 (notes).md", "# Units\n")
        self.write("guide(1).md", "# Units\n")
        report = self.audit('[Guide](<guide%20%231%20(notes).md?raw=1#units> "Title")\n'
                            '[Guide](guide(1).md#units)\n'
                            '[Guide](guide\\(1\\).md#units "Title")\n')
        self.assertEqual(report.checked, 3)
        self.assertEqual(report.failures, [])

    def test_missing_markdown_heading_fails(self):
        report = self.audit("# Here\n[Broken](#elsewhere)\n")
        self.assertIn("Missing heading", report.failures[0])

    def test_source_line_ranges_are_bounded_and_ordered(self):
        self.write("source.jsonl", '{}\n{}\n{}')
        report = self.audit('[Good](source.jsonl#L1-L3)\n[Good](source.jsonl#L3)\n'
                            '[Past end](source.jsonl#L4)\n[Reversed](source.jsonl#L3-L2)\n'
                            '[Zero](source.jsonl#L0)\n')
        self.assertEqual(report.checked, 5)
        self.assertEqual(len(report.failures), 3)
        self.assertTrue(all("Invalid source lines" in f for f in report.failures))

    def test_only_known_absent_corpora_are_optional(self):
        text = ('[Full](dataset/junction-dataset/questions.jsonl#L2)\n'
                '[Typo](dataset/junction-dataset-typo/questions.jsonl)\n')
        report = self.audit(text)
        self.assertEqual(report.optional, 1)
        self.assertEqual(len(report.failures), 1)
        (self.root / "dataset/junction-dataset").mkdir(parents=True)
        report = self.audit(text)
        self.assertEqual(report.optional, 0)
        self.assertEqual(len(report.failures), 2)

    def test_external_urls_skip_network_and_root_links_use_repository(self):
        report = self.audit('# Guide\n[Root](/README.md#guide)\n'
                            '[External](https://example.invalid/page)\n'
                            '[External](//example.invalid/page)\n'
                            '[Mail](mailto:example@example.invalid)\n')
        self.assertEqual(report.checked, 1)
        self.assertEqual(report.failures, [])

    def test_malformed_url_is_a_failure_instead_of_a_crash(self):
        report = self.audit("[Broken](https://[invalid)\n")
        self.assertIn("Invalid target URL", report.failures[0])

    def test_wrong_case_links_fail_on_windows_and_linux(self):
        self.write("Guide.md", "# Guide\n")
        report = self.audit("[Broken](guide.md)\n")
        self.assertIn("Case mismatch", report.failures[0])

    def test_links_outside_checkout_fail(self):
        report = self.audit("[Outside](../outside.md)\n")
        self.assertIn("Target outside repository", report.failures[0])

    def test_git_inventory_includes_nested_reports_and_excludes_archives(self):
        names = ["README.md", "docs/nested/guide.md",
                 "experiments/runs/pilot/example/README.md",
                 "dataset/junction-dataset/README.md"]
        for name in names:
            self.write(name)
        completed = subprocess.CompletedProcess([], 0, "\0".join(names).encode(), b"")
        with patch("scripts.check_docs.subprocess.run", return_value=completed):
            paths = documents(self.root)
        self.assertEqual({p.relative_to(self.root).as_posix() for p in paths}, set(names[:3]))

    def test_without_git_nested_docs_still_checked(self):
        names = ["README.md", "docs/nested/guide.md",
                 "experiments/runs/pilot/example/README.md", "frontend/README.md",
                 "dataset/junction-dataset/README.md"]
        for name in names:
            self.write(name)
        with patch("scripts.check_docs.subprocess.run", side_effect=FileNotFoundError):
            paths = documents(self.root)
        self.assertEqual({p.relative_to(self.root).as_posix() for p in paths}, set(names[:4]))


if __name__ == "__main__":
    unittest.main()
