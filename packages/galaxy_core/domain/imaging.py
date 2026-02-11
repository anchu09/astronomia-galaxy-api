"""Domain types for target resolution and catalog image fetching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Band / range as requested by user; maps to a SkyView survey name.
Band = Literal["visible", "optical", "infrared", "ir", "ultraviolet", "uv"]

# SkyView survey identifiers (subset used by our band mapping).
SurveyName = str

# Map band (user-facing) to default SkyView survey. Agent or options can override with catalog=.
BAND_TO_SURVEY: dict[str, SurveyName] = {
    "visible": "DSS",
    "optical": "DSS",
    "infrared": "2MASS-J",
    "ir": "2MASS-J",
    "ultraviolet": "GALEX",
    "uv": "GALEX",
}


@dataclass(frozen=True)
class ResolvedTarget:
    """Result of resolving a target and fetching an image from a catalog."""

    ra_deg: float
    dec_deg: float
    name: str | None
    survey_used: str
    image_url: str
    size_arcmin: float
