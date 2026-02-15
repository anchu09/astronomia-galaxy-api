from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from packages.galaxy_agent.artifacts import ArtifactStore
from packages.galaxy_agent.domain.models import TaskType
from packages.galaxy_agent.langchain_backend import LangChainBackend
from packages.galaxy_agent.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Provenance,
    Target,
)
from packages.galaxy_agent.orchestrator import TaskOrchestrator
from packages.galaxy_core.analyzer import BasicGalaxyAnalyzer

logger = logging.getLogger(__name__)

_DEFAULT_TASK: TaskType = "morphology_summary"


class AgentRunner:
    """Main entrypoint for request->response orchestration (LangChain)."""

    def __init__(
        self,
        artifact_dir: str = "artifacts",
        langsmith_enabled: bool = False,
    ) -> None:
        self.langsmith_enabled = langsmith_enabled
        self.analyzer = BasicGalaxyAnalyzer()
        self.orchestrator = TaskOrchestrator(
            analyzer=self.analyzer,
            artifact_store=ArtifactStore(artifact_dir),
        )
        self.langchain_backend = LangChainBackend()

    def run(self, request: AnalyzeRequest) -> AnalyzeResponse:
        try:
            enriched = self.langchain_backend.enrich_request(request)
            resolved = self._resolve_request(enriched)
            self._prepare_llm_plan(resolved)
            return self.orchestrator.run(request=resolved, langsmith_enabled=self.langsmith_enabled)
        except Exception:
            logger.exception(
                "analysis_failed",
                extra={"request_id": request.request_id, "event": "error"},
            )
            return AnalyzeResponse(
                request_id=request.request_id,
                status="error",
                summary="No se pudo completar el análisis. Revisa los logs o inténtalo de nuevo.",
                results={},
                artifacts=[],
                provenance=Provenance(
                    versions={
                        "galaxy_core": "0.1.0",
                        "galaxy_agent": "0.1.0",
                        "langsmith_enabled": str(self.langsmith_enabled).lower(),
                    }
                ),
                warnings=[],
            )

    def _resolve_request(self, request: AnalyzeRequest) -> AnalyzeRequest:
        """Ensure target and task are set; normalize message -> messages.
        For NL-only input use defaults (later: LLM intent extraction).
        """
        if request.target is not None and request.task is not None:
            return request
        # NL path: default target/task so orchestrator can run
        target = request.target or Target(name="from conversation")
        task: TaskType = request.task if request.task is not None else _DEFAULT_TASK
        return request.to_resolved_request(target=target, task=task)

    def _prepare_llm_plan(self, request: AnalyzeRequest) -> None:
        """Scaffold: future LLM tool-calling runs here; uses normalized messages when present."""
        _ = self.langchain_backend.build_prompt(request)
        _ = self.langchain_backend.plan_tool_calls(request)

    def run_stream(self, request: AnalyzeRequest) -> Iterator[dict[str, Any]]:
        """Yields SSE-style events: status, summary, artifacts, end (or error)."""
        try:
            enriched = self.langchain_backend.enrich_request(request)
            resolved = self._resolve_request(enriched)
            self._prepare_llm_plan(resolved)
            yield from self.orchestrator.run_stream(
                request=resolved, langsmith_enabled=self.langsmith_enabled
            )
        except Exception as e:
            logger.exception(
                "analysis_failed",
                extra={"request_id": request.request_id, "event": "error"},
            )
            yield {"type": "error", "message": str(e)}
