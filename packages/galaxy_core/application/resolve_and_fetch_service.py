"""Resolve target (name or coordinates) and fetch image URL from catalog."""

from __future__ import annotations

from packages.galaxy_core.domain.imaging import BAND_TO_SURVEY, ResolvedTarget
from packages.galaxy_core.infrastructure.sdss_client import get_image_url as sdss_get_image_url
from packages.galaxy_core.infrastructure.sesame_client import resolve as sesame_resolve
from packages.galaxy_core.infrastructure.skyview_client import (
    get_image_url as skyview_get_image_url,
)


def resolve_and_fetch(
    name: str | None = None,
    ra_deg: float | None = None,
    dec_deg: float | None = None,
    band: str | None = None,
    catalog: str | None = None,
    size_arcmin: float = 10.0,
) -> ResolvedTarget:
    """Resolve target by name or coordinates and get image URL from SkyView.

    Exactly one of (name) or (ra_deg and dec_deg) must be provided.
    Exactly one of (band) or (catalog) must be provided.
    size_arcmin is passed through to the image request (for display/analysis scale).

    Band maps to a default survey (e.g. visible -> DSS, ir -> 2MASS-J).
    Catalog is used as the SkyView survey name directly (e.g. SDSS, GALEX).
    """
    if name is not None and name.strip() != "":
        if ra_deg is not None or dec_deg is not None:
            raise ValueError("Provide either name or (ra_deg, dec_deg), not both.")
        ra_deg, dec_deg = sesame_resolve(name.strip())
        resolved_name: str | None = name.strip()
    elif ra_deg is not None and dec_deg is not None:
        resolved_name = None
    else:
        raise ValueError("Provide either name or (ra_deg, dec_deg).")

    survey_str: str
    if catalog is not None and catalog.strip() != "":
        survey_str = catalog.strip()
    elif band is not None and band.strip() != "":
        s = BAND_TO_SURVEY.get(band.strip().lower())
        if s is None:
            raise ValueError(
                f"Unknown band '{band}'. Use one of: {list(BAND_TO_SURVEY.keys())}"
            )
        survey_str = s
    else:
        raise ValueError("Provide either band or catalog.")

    if survey_str.upper() == "SDSS":
        # SDSS: direct URL, no network call (fast; coverage mainly northern sky).
        image_url = sdss_get_image_url(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            size_arcmin=size_arcmin,
        )
    else:
        image_url = skyview_get_image_url(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            survey=survey_str,
            size_arcmin=size_arcmin,
        )

    return ResolvedTarget(
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        name=resolved_name,
        survey_used=survey_str,
        image_url=image_url,
        size_arcmin=size_arcmin,
    )
