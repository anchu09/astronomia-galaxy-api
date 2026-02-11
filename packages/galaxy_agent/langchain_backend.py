from __future__ import annotations

from packages.galaxy_agent.models import AnalyzeRequest


class LangChainBackend:
    """Placeholder for future LangChain prompt/tool-calling integration."""

    def build_prompt(self, request: AnalyzeRequest) -> str:
        target_name = request.target.name if request.target else "unknown"
        task = request.task or "morphology_summary"
        return (
            "You are a galaxy analysis assistant. "
            f"Task={task}, target={target_name}, "
            f"request_id={request.request_id}."
        )

    def plan_tool_calls(self, request: AnalyzeRequest) -> list[str]:
        task_to_tools = {
            "segment": ["tool_segment"],
            "measure_basic": ["tool_segment", "tool_measure_basic"],
            "morphology_summary": [
                "tool_segment",
                "tool_measure_basic",
                "tool_morphology_summary",
                "tool_generate_report",
            ],
        }
        task = request.task or "morphology_summary"
        return task_to_tools.get(task, task_to_tools["morphology_summary"])
