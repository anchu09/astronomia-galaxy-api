from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from typing import Any

import requests

from packages.galaxy_agent.artifacts import ArtifactStore
from packages.galaxy_agent.langchain_backend import LangChainBackend
from packages.galaxy_agent.models import AnalyzeRequest, AnalyzeResponse, Artifact, Provenance
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
    """REQUESTS_VERIFY_SSL env (default true). Set false for certificate errors (e.g. Zscaler)."""
    val = os.environ.get("REQUESTS_VERIFY_SSL", "true").strip().lower()
    return val not in ("0", "false", "no", "off")


def _last_user_message(request: AnalyzeRequest) -> str:
    """Último mensaje del usuario para que el agente responda a lo que preguntó."""
    msgs = request.get_normalized_messages()
    if msgs:
        last_user = next((m.content for m in reversed(msgs) if m.role == "user"), None)
        if last_user:
            return last_user
    return request.message or ""


class TaskOrchestrator:
    def __init__(
        self,
        analyzer: BasicGalaxyAnalyzer,
        artifact_store: ArtifactStore,
        langchain_backend: LangChainBackend | None = None,
    ) -> None:
        self.analyzer = analyzer
        self.artifact_store = artifact_store
        self.langchain_backend = langchain_backend

    def run(self, request: AnalyzeRequest, langsmith_enabled: bool) -> AnalyzeResponse:
        for event in self.run_stream(request, langsmith_enabled):
            if event.get("type") == "end":
                artifacts_d = event.get("artifacts", [])
                prov = event.get("provenance")
                return AnalyzeResponse(
                    request_id=event["request_id"],
                    status=event["status"],
                    summary=event.get("summary", ""),
                    results=event.get("results", {}),
                    artifacts=[Artifact(**a) for a in artifacts_d],
                    provenance=Provenance(**prov) if isinstance(prov, dict) else prov,
                    warnings=event.get("warnings", []),
                )
            if event.get("type") == "error":
                raise RuntimeError(event.get("message", "Unknown error"))
        raise RuntimeError("Stream ended without end event")

    def run_stream(
        self, request: AnalyzeRequest, langsmith_enabled: bool
    ) -> Iterator[dict[str, Any]]:
        artifacts: list[Artifact] = []
        warnings: list[str] = []

        if request.image_url is None and request.target is not None:
            yield {"type": "status", "message": "Resolviendo galaxia y descargando imagen…"}
            request = self._resolve_fetch_and_download(request)
            yield {"type": "status", "message": "Imagen descargada."}

        if request.image_url:
            artifacts.append(Artifact(type="image", path=request.image_url))

        if request.task == "fetch_image":
            # Solo imagen: respuesta concisa. Siempre indicar banda efectiva (p. ej. visible por defecto)
            # para que en el siguiente turno el usuario/LLM sepan qué banda se usó.
            target_name = (request.target and request.target.name) or "galaxia"
            opts = request.options or {}
            band = opts.get("band")
            effective_band = str(band) if band else "visible"  # default en _resolve_fetch = SDSS
            user_message = _last_user_message(request)
            if self.langchain_backend:
                summary = self.langchain_backend.generate_image_caption(
                    target_name=str(target_name),
                    band=effective_band,
                    user_message=user_message or None,
                )
            else:
                summary = f"Aquí tienes la imagen de {target_name} en banda {effective_band}."
            results = {}
        else:
            # Análisis: segmentación, medidas y opcionalmente resumen morfológico
            yield {"type": "status", "message": "Segmentando imagen…"}
            image = load_image(request.image_url)
            segmentation = tool_segment(self.analyzer, image)
            artifacts.append(self.artifact_store.save_mask(request.request_id, segmentation.mask))

            results = {"segmentation_metadata": segmentation.metadata}
            summary = "Segmentation completed."

            if request.task in ("measure_basic", "morphology_summary"):
                yield {"type": "status", "message": "Calculando medidas…"}
                measurements = tool_measure_basic(self.analyzer, image, segmentation.mask)
                results["measurements"] = measurements
                artifacts.append(
                    self.artifact_store.save_measurements(request.request_id, measurements)
                )
                summary = "Basic measurements computed."

            if request.task == "morphology_summary":
                yield {"type": "status", "message": "Generando resumen…"}
                morphology_text = tool_morphology_summary(
                    self.analyzer,
                    results["measurements"],
                )
                report_text = tool_generate_report(request.request_id, morphology_text, results)
                artifacts.append(self.artifact_store.save_report(request.request_id, report_text))
                if self.langchain_backend:
                    target_name = (request.target and request.target.name) or "galaxia"
                    opts = request.options or {}
                    band = opts.get("band")
                    effective_band = str(band) if band else "visible"
                    summary = self.langchain_backend.generate_accompanying_summary(
                        target_name=str(target_name),
                        band=effective_band,
                        morphology_summary=morphology_text,
                        user_message=_last_user_message(request) or None,
                    )
                else:
                    summary = morphology_text

        logger.info(
            "analysis_completed",
            extra={"request_id": request.request_id, "task": request.task, "event": "analysis"},
        )

        response = self._build_response(
            request, summary, results, artifacts, warnings, langsmith_enabled
        )
        yield {"type": "summary", "summary": response.summary}
        if artifacts:
            yield {"type": "artifacts", "request_id": request.request_id}
        yield {
            "type": "end",
            "request_id": response.request_id,
            "status": response.status,
            "summary": response.summary,
            "results": response.results,
            "artifacts": [a.model_dump() for a in response.artifacts],
            "provenance": response.provenance.model_dump(),
            "warnings": response.warnings,
        }

    def _resolve_fetch_and_download(self, request: AnalyzeRequest) -> AnalyzeRequest:
        """Resolve target (by name or options ra_deg/dec_deg), get image URL, download, save.

        options may contain: catalog, band, size_arcmin, ra_deg, dec_deg.
        - If ra_deg and dec_deg in options → resolve by coordinates; else by target.name.
        - catalog or band (visible, infrared, uv, etc.) choose survey; default catalog SDSS.
        - For visible/optical bands we prefer SDSS first and fall back to the band-mapped survey.
        """
        opts = request.options or {}
        ra_opt = opts.get("ra_deg")
        dec_opt = opts.get("dec_deg")
        catalog_opt = opts.get("catalog")
        band_opt = opts.get("band")
        size_opt = float(opts.get("size_arcmin", 10.0))
        # Build a small ordered list of (catalog, band) attempts so we can be
        # robust to gaps in coverage (e.g. SDSS footprint) and flaky services
        # (e.g. SkyView). Exactly one of catalog or band is non-None per entry.
        attempts: list[tuple[str | None, str | None]] = []
        if catalog_opt:
            # Caller explicitly requested a catalog; honor it as the only attempt.
            attempts.append((str(catalog_opt).strip(), None))
        elif band_opt:
            band_str = str(band_opt).strip()
            band_lower = band_str.lower()
            # For optical/visible bands, prefer SDSS first (fast, direct URL)
            # and fall back to the SkyView-mapped survey for that band.
            if band_lower in ("visible", "optical"):
                attempts.append(("SDSS", None))
            attempts.append((None, band_str))
        else:
            # No catalog/band specified: default to SDSS for a quick optical view.
            attempts.append(("SDSS", None))

        errors: list[str] = []

        for catalog_param, band_param in attempts:
            try:
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
            except Exception as exc:  # noqa: BLE001
                label = catalog_param or band_param or "default"
                logger.warning(
                    "image_fetch_failed",
                    extra={
                        "request_id": request.request_id,
                        "catalog": catalog_param,
                        "band": band_param,
                        "error": str(exc),
                        "event": "image_fetch_error",
                        "attempt": label,
                    },
                )
                errors.append(f"{label}: {exc}")
                continue

        # If we exhaust all attempts, bubble up a clear error so the agent and
        # user can see what was tried.
        raise RuntimeError(
            f"Failed to resolve and fetch image after {len(attempts)} attempt(s): "
            + "; ".join(errors)
        )

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
