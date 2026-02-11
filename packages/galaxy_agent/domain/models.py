from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

TaskType = Literal["morphology_summary", "segment", "measure_basic"]
ResponseStatus = Literal["success", "error"]
ArtifactType = Literal["mask", "plot", "report", "image"]


class Target(BaseModel):
    name: str


class ChatMessage(BaseModel):
    """Single message in a conversation (user or assistant)."""

    role: Literal["user", "assistant"]
    content: str


class AnalyzeRequest(BaseModel):
    """Request for galaxy analysis. Supports hybrid input: natural language or structured."""

    request_id: str
    # Natural language: one of these (or both; messages takes precedence over message)
    message: str | None = None
    messages: list[ChatMessage] | None = None
    # Structured (optional when message/messages provided)
    target: Target | None = None
    task: TaskType | None = None
    image_url: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_message_or_structured(self) -> AnalyzeRequest:
        has_nl = (self.message is not None and self.message.strip() != "") or (
            self.messages is not None and len(self.messages) > 0
        )
        has_structured = self.target is not None and self.task is not None
        if not has_nl and not has_structured:
            raise ValueError(
                "Provide natural language (message or messages) or structured (target and task)."
            )
        return self

    def get_normalized_messages(self) -> list[ChatMessage]:
        """Return messages list: from messages if set, else from message (single user turn)."""
        if self.messages is not None and len(self.messages) > 0:
            return self.messages
        if self.message is not None and self.message.strip() != "":
            return [ChatMessage(role="user", content=self.message.strip())]
        return []

    def to_resolved_request(self, target: Target, task: TaskType) -> AnalyzeRequest:
        """Build a request with guaranteed target and task (for orchestrator)."""
        return AnalyzeRequest(
            request_id=self.request_id,
            message=self.message,
            messages=self.messages,
            target=target,
            task=task,
            image_url=self.image_url,
            options=self.options,
        )


class Artifact(BaseModel):
    type: ArtifactType
    path: str


class Provenance(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    versions: dict[str, str]


class AnalyzeResponse(BaseModel):
    request_id: str
    status: ResponseStatus
    summary: str
    results: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    provenance: Provenance
    warnings: list[str] = Field(default_factory=list)
