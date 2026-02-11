#!/usr/bin/env python3
"""Test resolve-and-fetch locally (no agent, no API).

Run from repo root:
  uv run python scripts/test_resolve_and_fetch.py
  uv run python scripts/test_resolve_and_fetch.py --sesame-only

Examples: first one uses SDSS (instant URL); rest use SkyView (can be slow).
Use --sesame-only to test name resolution only. catalog=SDSS avoids SkyView.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests

# Run from repo root so packages are importable.
sys.path.insert(0, ".")

from packages.galaxy_core.application.resolve_and_fetch_service import resolve_and_fetch
from packages.galaxy_core.infrastructure.sesame_client import resolve as sesame_resolve

# Cap timeouts in this script so it doesn't hang (SESAME and SkyView can be slow).
SCRIPT_SESAME_TIMEOUT_SEC = 30
SCRIPT_SKYVIEW_TIMEOUT_SEC = 90


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test resolve-and-fetch (SESAME + SkyView)"
    )
    parser.add_argument(
        "--sesame-only",
        action="store_true",
        help="Only test name resolution (SESAME); skip SkyView image fetch",
    )
    parser.add_argument(
        "--skyview-timeout",
        type=int,
        default=None,
        metavar="SEC",
        help=f"SkyView timeout in seconds (default: {SCRIPT_SKYVIEW_TIMEOUT_SEC} or env SKYVIEW_TIMEOUT)",
    )
    args = parser.parse_args()

    if args.sesame_only:
        print("--- SESAME-only mode: resolving names to (ra, dec) ---")
        names = ["M81", "NGC 1300", "NGC 4321"]
        for name in names:
            try:
                ra, dec = sesame_resolve(name)
                print(f"  {name!r} -> ra={ra:.4f} dec={dec:.4f}")
            except Exception as e:
                print(f"  {name!r} -> ERROR: {e}")
        print("\nDone.")
        return

    # So the script doesn't hang: use short timeouts unless user already set env.
    if not os.environ.get("SESAME_TIMEOUT"):
        os.environ["SESAME_TIMEOUT"] = str(SCRIPT_SESAME_TIMEOUT_SEC)
    if args.skyview_timeout is not None:
        os.environ["SKYVIEW_TIMEOUT"] = str(args.skyview_timeout)
    elif not os.environ.get("SKYVIEW_TIMEOUT"):
        os.environ["SKYVIEW_TIMEOUT"] = str(SCRIPT_SKYVIEW_TIMEOUT_SEC)
    print(
        f"Timeouts: SESAME={os.environ.get('SESAME_TIMEOUT')}s, "
        f"SkyView={os.environ.get('SKYVIEW_TIMEOUT')}s. "
        "Set SESAME_TIMEOUT/SKYVIEW_TIMEOUT or --skyview-timeout to override."
    )

    examples: list[dict[str, Any]] = [
        # SDSS: direct URL, no network wait (good first test).
        {"name": "M81", "catalog": "SDSS", "size_arcmin": 10.0},
        {"name": "M81", "band": "visible", "size_arcmin": 10.0},
        {"name": "M81", "band": "infrared", "size_arcmin": 10.0},
        {"name": "NGC 1300", "band": "optical", "size_arcmin": 8.0},
        {"name": "NGC 4321", "catalog": "DSS", "size_arcmin": 12.0},
        {
            "ra_deg": 148.888,
            "dec_deg": 69.065,
            "catalog": "2MASS-J",
            "size_arcmin": 5.0,
        },
    ]

    for i, kwargs in enumerate(examples, 1):
        print(f"\n--- Example {i}: {kwargs} ---")
        try:
            result = resolve_and_fetch(**kwargs)
            print(f"  ra_deg={result.ra_deg:.4f}  dec_deg={result.dec_deg:.4f}")
            print(f"  name={result.name!r}  survey_used={result.survey_used!r}")
            print(f"  size_arcmin={result.size_arcmin}")
            url_preview = (
                result.image_url[:80] + "..."
                if len(result.image_url) > 80
                else result.image_url
            )
            print(f"  image_url={url_preview}")
        except requests.exceptions.Timeout as e:
            print(
                f"  ERROR: Timeout ({e}). "
                "SESAME/SkyView can be slow. Try --skyview-timeout N or --sesame-only."
            )
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
