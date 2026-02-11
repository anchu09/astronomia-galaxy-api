#!/usr/bin/env python3
"""Test resolve + fetch + analysis with multiple galaxies, bands, catalogs, and coordinates.

Covers: target by name, target by coordinates (ra/dec in options), band (visible, infrared, uv),
catalog (SDSS, DSS, 2MASS-J, GALEX). Uses full pipeline: resolve → download → segment → measure.

Run from repo root:
  uv run python scripts/test_analyze_multi.py
  REQUESTS_VERIFY_SSL=false uv run python scripts/test_analyze_multi.py   # if behind Zscaler

  --sdss-only     Only run cases that use SDSS (no SkyView). Use when SkyView times out.
  --no-analysis   Only resolve + download; skip segment/measure (faster, fewer deps).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.galaxy_agent.agent_runner import AgentRunner
from packages.galaxy_agent.models import AnalyzeRequest, Target

# Cases: (request_id_suffix, target_name or None for coords, options dict).
# When target_name is None, options must have ra_deg and dec_deg.
CASES = [
    # By name + catalog
    ("m81-sdss", "M81", {"catalog": "SDSS"}),
    ("m81-dss", "M81", {"catalog": "DSS"}),
    ("m81-2mass", "M81", {"catalog": "2MASS-J"}),
    ("m81-galex", "M81", {"catalog": "GALEX"}),
    # By name + band (maps to survey)
    ("m81-visible", "M81", {"band": "visible"}),
    ("m81-infrared", "M81", {"band": "infrared"}),
    ("m81-uv", "M81", {"band": "uv"}),
    ("ngc1300-sdss", "NGC 1300", {"catalog": "SDSS"}),
    ("ngc4321-sdss", "NGC 4321", {"catalog": "SDSS"}),
    # By coordinates + catalog/band (no name resolution)
    ("coord-sdss", None, {"ra_deg": 148.888, "dec_deg": 69.065, "catalog": "SDSS"}),
    ("coord-infrared", None, {"ra_deg": 148.888, "dec_deg": 69.065, "band": "infrared"}),
]

# SDSS footprint is mainly northern; NGC 1300 (southern) may 404 with --sdss-only.
SDSS_ONLY_CASES = [
    ("m81-sdss", "M81", {"catalog": "SDSS"}),
    ("ngc1300-sdss", "NGC 1300", {"catalog": "SDSS"}),  # may 404 (southern)
    ("ngc4321-sdss", "NGC 4321", {"catalog": "SDSS"}),
    ("coord-sdss", None, {"ra_deg": 148.888, "dec_deg": 69.065, "catalog": "SDSS"}),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-case resolve/fetch/analyze test")
    parser.add_argument(
        "--sdss-only",
        action="store_true",
        help="Only run SDSS cases (no SkyView; use when SkyView times out)",
    )
    parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Only resolve + download; skip segment/measure (task=segment only still runs)",
    )
    args = parser.parse_args()

    cases = SDSS_ONLY_CASES if args.sdss_only else CASES
    if args.sdss_only:
        print("Running SDSS-only cases (skip SkyView).\n")

    runner = AgentRunner(artifact_dir="artifacts", langsmith_enabled=False)
    passed = 0
    failed = 0

    for suffix, target_name, options in cases:
        request_id = f"multi-{suffix}"
        target = Target(name=target_name or "coordinates")
        request = AnalyzeRequest(
            request_id=request_id,
            target=target,
            task="segment" if args.no_analysis else "morphology_summary",
            options=options,
        )
        label = f"{target_name or 'coord'} {options}"
        print(f"--- {request_id}: {label} ---")
        try:
            response = runner.run(request)
            if response.status == "success":
                print(f"  OK: {response.summary[:80]}...")
                passed += 1
            else:
                print(f"  FAIL: {response.status} {response.results.get('detail', '')}")
                failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
        print()

    print(f"Done: {passed} passed, {failed} failed.")
    if failed > 0:
        print(
            "Note: SkyView (DSS, 2MASS-J, GALEX) often times out or fails from corporate networks; "
            "NGC 1300 is outside SDSS footprint. Use --sdss-only to run only SDSS cases."
        )


if __name__ == "__main__":
    main()
