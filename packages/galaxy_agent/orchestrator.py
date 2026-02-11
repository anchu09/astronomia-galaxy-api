from __future__ import annotations

import logging
import os
from typing import Any

import requests

from packages.galaxy_agent.artifacts import ArtifactStore
from packages.galaxy_agent.models import AnalyzeRequest, AnalyzeResponse, Provenance
from packages.galaxy_agent.tools import (
    load_image,
    tool_generate_report,
    tool_measure_basic,
    tool_morphology_summary,
    tool_segment,
)
from packages.galaxy_core.analyzer import BasicGalaxyAnalyzer
from packages.galaxy_core.application.resolve_and_fetch_service import resolve_and_fetch

logger = logging.getLogger(__name__)

# Timeout for downloading the image after we have its URL (e.g. SDSS, SkyView result).
IMAGE_DOWNLOAD_TIMEOUT_SEC = 30


def _ssl_verify() -> bool:
    """Use REQUESTS_VERIFY_SSL env (default true). Set to false if you get certificate errors (e.g. Zscaler)."""
    val = os.environ.get("REQUESTS_VERIFY_SSL", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


class TaskOrchestrator:
    def __init__(self, analyzer: BasicGalaxyAnalyzer, artifact_store: ArtifactStore) -> None:
        self.analyzer = analyzer
        self.artifact_store = artifact_store

    def run(self, request: AnalyzeRequest, langsmith_enabled: bool) -> AnalyzeResponse:
        artifacts = []
        warnings: list[str] = []

        # If we have a target but no image yet: resolve name → get URL → download → save for analysis.
        if request.image_url is None and request.target is not None:
            request = self._resolve_fetch_and_download(request)

        image = load_image(request.image_url)
        segmentation = tool_segment(self.analyzer, image)
        artifacts.append(self.artifact_store.save_mask(request.request_id, segmentation.mask))

        results: dict[str, Any] = {"segmentation_metadata": segmentation.metadata}
        summary = "Segmentation completed."

        if request.task in ("measure_basic", "morphology_summary"):
            measurements = tool_measure_basic(self.analyzer, image, segmentation.mask)
            results["measurements"] = measurements
            artifacts.append(
                self.artifact_store.save_measurements(request.request_id, measurements)
            )
            summary = "Basic measurements computed."

        if request.task == "morphology_summary":
            summary = tool_morphology_summary(
                self.analyzer,
                results["measurements"],
            )
            report_text = tool_generate_report(request.request_id, summary, results)
            artifacts.append(self.artifact_store.save_report(request.request_id, report_text))

        logger.info(
            "analysis_completed",
            extra={"request_id": request.request_id, "task": request.task, "event": "analysis"},
        )

        return self._build_response(request, summary, results, artifacts, warnings, langsmith_enabled)

    def _resolve_fetch_and_download(self, request: AnalyzeRequest) -> AnalyzeRequest:
        """Resolve target (by name or options ra_deg/dec_deg), get image URL, download, save.

        options may contain: catalog, band, size_arcmin, ra_deg, dec_deg.
        - If ra_deg and dec_deg in options → resolve by coordinates; else by target.name.
        - catalog or band (visible, infrared, uv, etc.) choose survey; default catalog SDSS.
        """
        opts = request.options or {}
        ra_opt = opts.get("ra_deg")
        dec_opt = opts.get("dec_deg")
        catalog_opt = opts.get("catalog")
        band_opt = opts.get("band")
        size_opt = float(opts.get("size_arcmin", 10.0))
        # resolve_and_fetch needs exactly one of band or catalog; default SDSS for speed.
        if catalog_opt:
            catalog_param, band_param = str(catalog_opt).strip(), None
        elif band_opt:
            catalog_param, band_param = None, str(band_opt).strip()
        else:
            catalog_param, band_param = "SDSS", None

        if ra_opt is not None and dec_opt is not None:
            resolved = resolve_and_fetch(
                ra_deg=float(ra_opt),
                dec_deg=float(dec_opt),
                catalog=catalog_param,
                band=band_param,
                size_arcmin=size_opt,
            )
        else:
            name = (request.target and request.target.name or "").strip()
            if not name:
                raise ValueError(
                    "Target name is empty; provide target.name or options ra_deg/dec_deg."
                )
            resolved = resolve_and_fetch(
                name=name,
                catalog=catalog_param,
                band=band_param,
                size_arcmin=size_opt,
            )

        resp = requests.get(
            resolved.image_url,
            timeout=IMAGE_DOWNLOAD_TIMEOUT_SEC,
            verify=_ssl_verify(),
        )
        resp.raise_for_status()
        image_path = self.artifact_store.save_image(request.request_id, resp.content)
        return request.model_copy(update={"image_url": image_path})

    def _build_response(
        self,
        request: AnalyzeRequest,
        summary: str,
        results: dict[str, Any],
        artifacts: list,
        warnings: list[str],
        langsmith_enabled: bool,
    ) -> AnalyzeResponse:
        provenance = Provenance(
            versions={
                "galaxy_core": "0.1.0",
                "galaxy_agent": "0.1.0",
                "langsmith_enabled": str(langsmith_enabled).lower(),
            }
        )
        return AnalyzeResponse(
            request_id=request.request_id,
            status="success",
            summary=summary,
            results=results,
            artifacts=artifacts,
            provenance=provenance,
            warnings=warnings,
        )
