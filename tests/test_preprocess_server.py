"""Exercise the actual review HTTP boundary, including escaped image paths."""
from __future__ import annotations

import http.client
from pathlib import Path
import tempfile
import threading
import unittest

from drawing_preprocessor.server import make_review_server


# One transparent 1x1 PNG; exercise actual image bytes without an image library.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b49444154789c636000020000050001a5f645400000000049454e44ae426082"
)


class ReviewServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "review"
        self.root.mkdir()
        (self.root / "index.html").write_text("<html>Review</html>", encoding="utf-8")
        (self.root / "images").mkdir()
        (self.root / "images" / "drawing image.png").write_bytes(PNG)
        (self.parent / "outside.txt").write_text("private outside file", encoding="utf-8")
        self.server = make_review_server(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._close)

    def _close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, path: str, method: str = "GET") -> tuple[int, dict, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_loopback_index_and_png_are_served_without_file_scheme(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Review", body)
        self.assertEqual(headers["Cache-Control"], "no-cache")
        status, headers, body = self.request("/images/drawing%20image.png")
        self.assertEqual(status, 200)
        self.assertEqual(body, PNG)
        self.assertEqual(headers["Content-Type"], "image/png")

    def test_head_reports_image_length_without_image_body(self):
        status, headers, body = self.request("/images/drawing%20image.png", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(int(headers["Content-Length"]), len(PNG))
        self.assertEqual(body, b"")

    def test_percent_filename_is_decoded_only_once_for_file_lookup(self):
        (self.root / "100%20literal.txt").write_text("Literal filename", encoding="utf-8")
        self.assertEqual(self.request("/100%2520literal.txt")[2], b"Literal filename")

    def test_missing_file_and_directory_listing_are_not_exposed(self):
        for target in ("/missing.png", "/images/", "/images"):
            with self.subTest(target=target):
                self.assertEqual(self.request(target)[0], 404)

    def test_directory_with_its_own_index_is_supported(self):
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "index.html").write_text("Nested index", encoding="utf-8")
        self.assertEqual(self.request("/nested/")[2], b"Nested index")

    def test_traversal_including_repeated_url_encoding_is_rejected(self):
        for target in ("/../outside.txt", "/%2e%2e/outside.txt", "/%252e%252e/outside.txt",
                       "/%2e%2e%5coutside.txt", "/C:%5coutside.txt", "/images/../../outside.txt"):
            with self.subTest(target=target):
                status, _, body = self.request(target)
                self.assertEqual(status, 404)
                self.assertNotIn(b"private outside file", body)

    def test_escaped_symlink_is_not_served(self):
        link = self.root / "escaped.txt"
        try:
            link.symlink_to(self.parent / "outside.txt")
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation requires platform permissions")
        self.assertEqual(self.request("/escaped.txt")[0], 404)

    def test_root_without_local_index_is_rejected(self):
        empty = self.parent / "empty"
        empty.mkdir()
        with self.assertRaises(ValueError):
            make_review_server(empty)


if __name__ == "__main__":
    unittest.main()
