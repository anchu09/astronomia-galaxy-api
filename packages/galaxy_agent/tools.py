from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import numpy as np
import requests
from PIL import Image

from packages.galaxy_core.analyzer import BasicGalaxyAnalyzer, create_synthetic_image
from packages.galaxy_core.application.resolve_and_fetch_service import resolve_and_fetch
from packages.galaxy_core.domain import ResolvedTarget, SegmentationResult


def tool_resolve_and_fetch_image(
    name: str | None = None,
    ra_deg: float | None = None,
    dec_deg: float | None = None,
    band: str | None = None,
    catalog: str | None = None,
    size_arcmin: float = 10.0,
) -> ResolvedTarget:
    """Resolve target (name or coordinates) and fetch image URL from catalog/band."""
    return resolve_and_fetch(
        name=name,
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        band=band,
        catalog=catalog,
        size_arcmin=size_arcmin,
    )


def _ssl_verify() -> bool:
    """Use REQUESTS_VERIFY_SSL env (default true). Set to false if you get certificate errors."""
    val = os.environ.get("REQUESTS_VERIFY_SSL", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def load_image(image_url: str | None, timeout_seconds: int = 15) -> np.ndarray:
    """Load image from URL (http/https) or local path for downstream analysis."""
    if image_url is None:
        return create_synthetic_image()

    if image_url.startswith(("http://", "https://")):
        response = requests.get(
            image_url, timeout=timeout_seconds, verify=_ssl_verify()
        )
        response.raise_for_status()
        data = response.content
    else:
        # Local path (or file://)
        path = image_url.removeprefix("file://")
        data = Path(path).read_bytes()

    image = Image.open(io.BytesIO(data)).convert("L")
    return np.asarray(image, dtype=np.float32)


def tool_segment(
    analyzer: BasicGalaxyAnalyzer, image: np.ndarray
) -> SegmentationResult:
    return analyzer.segment_galaxy(image)


def tool_measure_basic(
    analyzer: BasicGalaxyAnalyzer, image: np.ndarray, mask: np.ndarray
) -> dict[str, float]:
    return analyzer.measure_basic(image, mask)


def tool_morphology_summary(
    analyzer: BasicGalaxyAnalyzer, measurements: dict[str, float]
) -> str:
    return analyzer.morphology_summary(measurements)


def tool_generate_report(request_id: str, summary: str, results: dict[str, Any]) -> str:
    return (
        f"Galaxy Analysis Report\n"
        f"request_id: {request_id}\n"
        f"summary: {summary}\n"
        f"results: {results}\n"
        f"note: report generator is a stub for MVP.\n"
    )
