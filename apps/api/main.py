from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI

from apps.api.auth import verify_api_key
from apps.api.config import Settings, get_settings
from packages.galaxy_agent.agent_runner import AgentRunner
from packages.galaxy_agent.logging_utils import setup_logging
from packages.galaxy_agent.models import AnalyzeRequest, AnalyzeResponse

app = FastAPI(title="Galaxy Agentic Chatbot API", version="0.1.0")
logger = logging.getLogger(__name__)


def get_runner(settings: Annotated[Settings | None, Depends(get_settings)] = None) -> AgentRunner:
    if settings is None:
        raise RuntimeError("Settings dependency not available")

    langsmith_enabled = bool(settings.langsmith_api_key) or settings.langsmith_tracing
    return AgentRunner(
        artifact_dir=settings.artifact_dir,
        langsmith_enabled=langsmith_enabled,
    )


@app.on_event("startup")
def on_startup() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("api_started", extra={"event": "startup"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(verify_api_key)])
def analyze(
    request: AnalyzeRequest,
    runner: Annotated[AgentRunner | None, Depends(get_runner)] = None,
) -> AnalyzeResponse:
    if runner is None:
        raise RuntimeError("Agent runner dependency not available")
    return runner.run(request)
