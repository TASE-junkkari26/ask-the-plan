"""Loopback-only static serving for a generated drawing review directory."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import os
from pathlib import Path
import shutil
from urllib.parse import unquote, urlsplit


def _resolve_request(root: Path, target: str) -> Path | None:
    """Return an existing scoped file, never a directory listing or escaped path."""
    try:
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            return None
        decoded = unquote(parsed.path, encoding="utf-8", errors="strict")
        probe = decoded
        # Reject nested URL-encoded traversal as well as ordinary ../ requests.
        # Normal filenames with spaces/Unicode still resolve through this path.
        for _ in range(5):
            if (not probe.startswith("/") or probe.startswith("//")
                    or "\\" in probe or ":" in probe or "\x00" in probe
                    or any(part in {".", ".."} for part in probe.split("/"))):
                return None
            next_probe = unquote(probe, encoding="utf-8", errors="strict")
            if probe == next_probe:
                break
            probe = next_probe
        else:
            return None
        path = (root / decoded.lstrip("/")).resolve()
        if not path.is_relative_to(root):
            return None
        if path.is_dir():
            path = (path / "index.html").resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None
        return path
    except (OSError, ValueError, UnicodeError):
        return None


def make_review_server(directory: Path, *, port: int = 0) -> ThreadingHTTPServer:
    """Create a static server bound exclusively to IPv4 loopback.

    The directory must contain index.html. Only files resolving below that root
    can be read, even if the request includes encoded traversal or an escaped
    symlink. Call shutdown/server_close when an embedded server is no longer used.
    """
    root = Path(directory).resolve()
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Review port must be an integer between 0 and 65535.")
    if not root.is_dir() or _resolve_request(root, "/") is None:
        raise ValueError("Review directory must contain a local index.html file.")

    class ReviewHandler(BaseHTTPRequestHandler):
        server_version = "AskThePlanReview/0.1"
        sys_version = ""

        def _serve(self, *, head: bool = False) -> None:
            path = _resolve_request(root, self.path)
            if path is None:
                self.send_error(404, "Review file not found")
                return
            try:
                stream = path.open("rb")
            except OSError:
                self.send_error(404, "Review file not found")
                return
            with stream:
                # Regenerating a gallery can replace this path after open; use
                # the actual opened file for Content-Length rather than its name.
                size = os.fstat(stream.fileno()).st_size
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if not head:
                    try:
                        shutil.copyfileobj(stream, self.wfile)
                    except (BrokenPipeError, ConnectionResetError):
                        pass  # A browser can cancel an image request on navigation.

        def do_GET(self) -> None:
            self._serve()

        def do_HEAD(self) -> None:
            self._serve(head=True)

    server = ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler)
    server.daemon_threads = True
    return server


def serve_review(directory: Path, *, port: int = 8765) -> None:
    """Serve a prepared gallery until Ctrl+C; never open a browser automatically."""
    server = make_review_server(directory, port=port)
    print(f"Review gallery: http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
