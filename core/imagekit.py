from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_RENDITION_DIMENSIONS: dict[int, tuple[int, int]] = {
    600: (600, 600),
    900: (900, 900),
    1200: (1200, 1200),
}


def safe_file_url(file_field: Any) -> str | None:
    if not file_field:
        return None
    try:
        return file_field.url
    except Exception:
        return None


def _safe_spec_url(spec_field: Any, fallback_url: str) -> str:
    try:
        return spec_field.url
    except Exception:
        return fallback_url


def _safe_spec_dimensions(spec_field: Any, fallback: tuple[int, int]) -> tuple[int, int]:
    try:
        width = int(spec_field.width)
        height = int(spec_field.height)
        if width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    return fallback


def build_responsive_rendition(
    *,
    original_field: Any,
    spec_map: Mapping[int, Any],
    largest_size: int,
) -> dict[str, Any] | None:
    """Return a resilient responsive image payload.

    If any ImageKit spec raises (e.g. S3 temporarily unavailable), this
    falls back to the original image URL and sensible default dimensions
    so templates can render without returning HTTP 500.
    """
    original_url = safe_file_url(original_field)
    if not original_url:
        return None

    ordered_sizes = sorted(spec_map)
    urls: dict[int, str] = {
        size: _safe_spec_url(spec_map[size], original_url) for size in ordered_sizes
    }

    fallback_dimensions = DEFAULT_RENDITION_DIMENSIONS.get(
        largest_size, (largest_size, largest_size)
    )
    width, height = _safe_spec_dimensions(spec_map[largest_size], fallback_dimensions)

    src = urls.get(largest_size, original_url)
    srcset = ", ".join(f"{urls[size]} {size}w" for size in ordered_sizes)

    return {
        "src": src,
        "srcset": srcset,
        "width": width,
        "height": height,
        "urls": urls,
    }
