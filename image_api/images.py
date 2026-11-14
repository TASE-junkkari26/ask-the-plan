"""Prepare an upright, bounded image without changing its scale or crop."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from .config import ApiSettings
from .errors import ApiError


@dataclass(frozen=True)
class PreparedImage:
    path: Path
    sha256: str
    inference_sha256: str
    width: int
    height: int
    inference_width: int | None = None
    inference_height: int | None = None
    preprocessing_mode: str = "off"
    prepared_id: str | None = None
    preparation_ms: float = 0
    preparation_cache_hit: bool | None = None

    @property
    def model_width(self) -> int:
        return self.width if self.inference_width is None else self.inference_width

    @property
    def model_height(self) -> int:
        return self.height if self.inference_height is None else self.inference_height


class _BoundedWriter:
    """Stop PNG encoding when its output would exceed the client limit."""

    def __init__(self, stream, limit: int):
        self.stream = stream
        self.limit = limit
        self.written = 0

    def write(self, data: bytes) -> int:
        if self.written + len(data) > self.limit:
            raise ApiError(413, "prepared_image_too_large", "The prepared image exceeds the inference image size limit.")
        result = self.stream.write(data)
        self.written += result
        return result

    def flush(self) -> None:
        self.stream.flush()


def prepare_image(content: bytes, settings: ApiSettings, directory: Path) -> PreparedImage:
    """The caller owns directory cleanup, including all failure paths."""
    if len(content) > settings.max_image_bytes:
        raise ApiError(413, "image_too_large", "The image exceeds the upload size limit.")
    if not content:
        raise ApiError(422, "invalid_image", "The image file is empty.")
    supported_header = (
        content.startswith(b"\x89PNG\r\n\x1a\n")
        or content.startswith(b"\xff\xd8\xff")
        or (content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    )
    if not supported_header:
        raise ApiError(415, "unsupported_image", "Supply one PNG, JPEG, or WebP image; render PDF/SVG views first.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ApiError(415, "unsupported_image", "Supply one PNG, JPEG, or WebP image.")
                if source.width * source.height > settings.max_pixels:
                    raise ApiError(413, "image_dimensions_too_large", "The image exceeds the decoded pixel limit.")
                if getattr(source, "n_frames", 1) != 1:
                    raise ApiError(422, "animated_image", "Supply a single still image, not an animation.")
                source.verify()
            with Image.open(BytesIO(content)) as source:
                source.load()
                with ImageOps.exif_transpose(source) as upright:
                    if "A" in upright.getbands() or "transparency" in upright.info:
                        # Give transparent input a defined drawing appearance.
                        with upright.convert("RGBA") as rgba:
                            image = Image.new("RGB", rgba.size, "white")
                            with rgba.getchannel("A") as alpha:
                                image.paste(rgba, mask=alpha)
                    else:
                        image = upright.convert("RGB")
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ApiError(413, "image_dimensions_too_large", "The image exceeds the decoded pixel limit.") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ApiError(422, "invalid_image", "The image could not be decoded; supply an intact supported image.") from None

    path = directory / "inference.png"
    width, height = image.size
    try:
        with image, path.open("wb") as stream:
            image.save(_BoundedWriter(stream, settings.max_image_bytes), format="PNG")
    except OSError:
        raise ApiError(500, "image_preparation_failed", "Could not prepare the image for inference.") from None
    return PreparedImage(
        path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        inference_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        width=width,
        height=height,
    )
