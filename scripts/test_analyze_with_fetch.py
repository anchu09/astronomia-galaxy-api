#!/usr/bin/env python3
"""Test full flow: target name → resolve + fetch image → download → segment/measure.

Run from repo root:
  uv run python scripts/test_analyze_with_fetch.py
  uv run python scripts/test_analyze_with_fetch.py M81
  uv run python scripts/test_analyze_with_fetch.py NGC 1300

Uses SDSS by default (fast). Image is saved under artifacts/<request_id>/image.jpg.
If you get SSL errors (e.g. behind Zscaler), run: REQUESTS_VERIFY_SSL=false uv run python scripts/test_analyze_with_fetch.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run from repo root so packages are importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.galaxy_agent.agent_runner import AgentRunner
from packages.galaxy_agent.models import AnalyzeRequest, Target


def main() -> None:
    name = "M81"
    if len(sys.argv) > 1:
        name = " ".join(sys.argv[1:]).strip() or name

    request = AnalyzeRequest(
        request_id="test-fetch-1",
        target=Target(name=name),
        task="morphology_summary",
        # image_url=None → orchestrator will resolve + fetch + download
    )

    print(f"Target: {request.target.name}")
    print("Resolving + fetching image (SDSS), then running analysis...\n")

    runner = AgentRunner(artifact_dir="artifacts", langsmith_enabled=False)
    response = runner.run(request)

    print(f"Status: {response.status}")
    print(f"Summary: {response.summary}")
    if response.results:
        print("Results:", response.results)
    if response.artifacts:
        print("Artifacts:", [a.model_dump() for a in response.artifacts])
    if response.warnings:
        print("Warnings:", response.warnings)

    # Image is at artifacts/<request_id>/image.jpg
    image_path = Path("artifacts") / request.request_id / "image.jpg"
    if image_path.exists():
        print(f"\nDownloaded image: {image_path}")


if __name__ == "__main__":
    main()
