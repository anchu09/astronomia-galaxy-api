"""SESAME name resolver: resolve object name to J2000 (RA, Dec) in degrees."""

from __future__ import annotations

import os
import re
import urllib.parse

import requests

# SESAME text format: "%J 148.88821940 +69.06529514" = RA Dec in decimal degrees
SESAME_JPOS_RE = re.compile(r"^%J\s+([+-]?[\d.]+)\s+([+-]?[\d.]+)", re.MULTILINE)

# HTTP first; CDS may redirect to HTTPS. SSL verify can be disabled via env (e.g. corporate proxy).
SESAME_URL = "http://cds.unistra.fr/cgi-bin/nph-sesame"
# Override with env SESAME_TIMEOUT (seconds) if needed.
TIMEOUT_SECONDS = 60


def _ssl_verify() -> bool:
    """Use REQUESTS_VERIFY_SSL env (default true). Set to false if you get certificate errors."""
    val = os.environ.get("REQUESTS_VERIFY_SSL", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def resolve(name: str) -> tuple[float, float]:
    """Resolve object name to J2000 (RA, Dec) in decimal degrees.

    Uses CDS SESAME service (SIMBAD/NED/VizieR). No fallbacks.

    Raises:
        ValueError: If name is empty or SESAME returns no position.
        requests.RequestException: On network error.
    """
    name = name.strip()
    if not name:
        raise ValueError("Object name cannot be empty")

    timeout_s = int(os.environ.get("SESAME_TIMEOUT", str(TIMEOUT_SECONDS)))
    url = f"{SESAME_URL}?-ox&{urllib.parse.quote(name)}"
    response = requests.get(url, timeout=timeout_s, verify=_ssl_verify())
    response.raise_for_status()
    text = response.text

    match = SESAME_JPOS_RE.search(text)
    if not match:
        if "Nothing found" in text:
            raise ValueError(f"SESAME returned no position for '{name}'")
        raise ValueError(f"SESAME returned no position for '{name}' (no %J line)")

    ra_deg = float(match.group(1))
    dec_deg = float(match.group(2))
    return (ra_deg, dec_deg)
