"""SDSS image URL builder: direct JPEG cutout URL (no network call).

SDSS SkyServer has a simple GET API; we only build the URL. Coverage is limited
(mainly northern sky). Use catalog=SDSS for fast optical previews when available.

API rules (to avoid 400): ra in [0,360], dec in [-90,90], scale in [0.015, 60.0],
width/height in [64, 2048]. Request must be GET with query params.
"""

from __future__ import annotations

import urllib.parse

# DR18 ImgCutout getjpeg (path per official docs).
SDSS_IMG_CUTOUT = "https://skyserver.sdss.org/dr18/SkyServerWS/ImgCutout/getjpeg"
DEFAULT_PIXELS = 300
SCALE_MIN, SCALE_MAX = 0.015, 60.0
SIZE_PIX_MIN, SIZE_PIX_MAX = 64, 2048


def get_image_url(
    ra_deg: float,
    dec_deg: float,
    size_arcmin: float = 10.0,
    pixels: int = DEFAULT_PIXELS,
) -> str:
    """Return the SDSS JPEG cutout URL for the given position and field size.

    Parameters are clamped to API ranges to avoid 400. No network request is made;
    the URL may 404 if the position is outside SDSS coverage. Callers must use GET.
    """
    ra = float(ra_deg) % 360.0
    dec = max(-90.0, min(90.0, float(dec_deg)))
    pixels = max(SIZE_PIX_MIN, min(SIZE_PIX_MAX, int(pixels)))
    scale_arcsec = (float(size_arcmin) * 60.0) / pixels
    scale_arcsec = max(SCALE_MIN, min(SCALE_MAX, scale_arcsec))

    params = {
        "ra": round(ra, 6),
        "dec": round(dec, 6),
        "scale": round(scale_arcsec, 4),
        "width": pixels,
        "height": pixels,
    }
    return f"{SDSS_IMG_CUTOUT}?{urllib.parse.urlencode(params)}"
