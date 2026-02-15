from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from packages.galaxy_agent.domain.models import Target, TaskType
from packages.galaxy_agent.models import AnalyzeRequest
from packages.galaxy_core.domain.imaging import get_capabilities_description


class LangChainBackend:
    """Backend para integrar un LLM (OpenAI) con el agente.

    MVP: usa el LLM solo para convertir lenguaje natural → parámetros estructurados
    (target/options) que luego consume el TaskOrchestrator. No ejecuta todavía
    tool-calling completo; en su lugar, pide al modelo que devuelva un JSON.
    """

    def __init__(self) -> None:
        self._model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        # El cliente usa OPENAI_API_KEY del entorno (no lo leemos aquí directamente).
        self._client = OpenAI()

    def enrich_request(self, request: AnalyzeRequest) -> AnalyzeRequest:
        """Usar el LLM para rellenar target/options a partir de mensajes NL.

        - Si ya viene target+task → no hace nada (devuelve el request tal cual).
        - Si no hay mensajes → tampoco hace nada.
        - Si hay mensajes NL y falta target/task → pide al LLM que extraiga:
          name, ra_deg/dec_deg, band, size_arcmin y construye un nuevo AnalyzeRequest.
        """
        if request.target is not None and request.task is not None:
            return request

        messages = request.get_normalized_messages()
        if not messages:
            return request

        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for natural language requests. "
                "Set it in .env and restart the container (or process)."
            )

        # Unir el historial en un solo texto sencillo para este MVP.
        conversation = "\n".join(f"{m.role}: {m.content}" for m in messages)

        system_prompt = (
            "You are an assistant for a system that ONLY does the following:\n"
            "- Show images of galaxies (by name, e.g. M87, or by coordinates), in bands: visible, infrared, or uv.\n"
            "- Optionally run basic morphology analysis on that image (segmentation, area, ellipticity, intensity).\n"
            "The system CANNOT: provide spectra, count stars, answer general astronomy questions, "
            "or do anything unrelated to galaxy images and this basic analysis.\n\n"
            "First decide: can_fulfill.\n"
            "- Set can_fulfill to false if the user asks for something we cannot do "
            "(e.g. 'dame el espectro', 'cuántas estrellas hay', 'qué es un agujero negro'), "
            "or if the message is not about galaxies/images/analysis.\n"
            "- Also set can_fulfill to false if the user is asking a FOLLOW-UP about what we already did "
            "(e.g. '¿en qué banda estaba la imagen?', '¿qué imagen me diste?', 'esa imagen en qué rango está?'). "
            "In that case, decline_reason must ANSWER from the conversation: look at the previous assistant "
            "message — if we said 'en banda visible' or 'banda visible', answer e.g. 'La imagen que te mostré "
            "fue en banda visible.' Do not start a new image request; just answer the question briefly.\n"
            "- Also set can_fulfill to false if the user asks ABOUT THE SYSTEM'S CAPABILITIES (e.g. '¿qué catálogos "
            "están disponibles?', '¿qué bandas soportáis?', '¿qué puede hacer esta aplicación?'). In that case, "
            "decline_reason must be a short, friendly answer in Spanish that includes this information:\n"
            "[CAPABILITIES]\n"
            f"{get_capabilities_description()}\n"
            "Rephrase it naturally; do not paste raw.\n"
            "When can_fulfill is false, you MUST set decline_reason: a short, natural message in Spanish. "
            "If it was a follow-up question, use the conversation to answer. If it was about capabilities, use [CAPABILITIES]. Otherwise:\n"
            "1) Acknowledge what they asked.\n"
            "2) Explain what this system can and cannot do.\n"
            "3) Suggest something we can do instead if relevant.\n"
            "Be friendly and concise. When can_fulfill is true, set decline_reason to null.\n\n"
            "CRITICAL - want_analysis: Set to true ONLY if the USER'S LAST MESSAGE (the current turn) explicitly "
            "asks for analysis. Keywords in that message: 'analiza', 'análisis', 'dame un análisis', 'medidas', "
            "'morfología', 'segmenta', 'resumen morfológico'. If the user only specifies which galaxy or band "
            "(e.g. 'de m104', 'm104', 'm104 en visible', 'la de m104') without asking for analysis IN THAT SAME MESSAGE, "
            "set want_analysis to FALSE. Do NOT infer from previous messages: e.g. if they said 'analiza la imagen' "
            "before and now say 'de m104', they are just answering which galaxy — set want_analysis to false, "
            "we will show only the image. Only run analysis when they ask for it in the same turn.\n\n"
            "Return ONLY a JSON object with these keys:\n"
            "- can_fulfill: boolean.\n"
            "- decline_reason: string or null (required when can_fulfill is false; null when true).\n"
            "- name: string or null (galaxy name).\n"
            "- ra_deg, dec_deg: number or null.\n"
            "- band: 'visible', 'infrared', 'uv' or null.\n"
            "- size_arcmin: number (default 10.0).\n"
            "- want_analysis: boolean (true ONLY if the last user message explicitly asks for analysis).\n"
            "If name and coordinates are both present, prefer coordinates but still return name.\n"
        )

        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": conversation},
            ],
        )

        content = response.choices[0].message.content or "{}"
        try:
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError:
            return request

        can_fulfill = data.get("can_fulfill", True)
        if isinstance(can_fulfill, str):
            can_fulfill = can_fulfill.strip().lower() in ("true", "1", "yes", "si")
        decline_reason = data.get("decline_reason")
        if isinstance(decline_reason, str):
            decline_reason = decline_reason.strip() or None
        if not can_fulfill and decline_reason:
            # Respuesta natural para lo no soportado; no ejecutamos pipeline
            target = request.target
            if target is None and data.get("name"):
                target = Target(name=str(data["name"]))
            task = "fetch_image"
            if data.get("want_analysis"):
                task = "morphology_summary"
            return AnalyzeRequest(
                request_id=request.request_id,
                message=request.message,
                messages=request.messages,
                target=target or Target(name=""),
                task=task,
                image_url=request.image_url,
                options=request.options or {},
                out_of_scope=True,
                decline_message=decline_reason,
            )

        name = data.get("name")
        ra_deg = data.get("ra_deg")
        dec_deg = data.get("dec_deg")
        band = data.get("band")
        size_arcmin = 10.0
        if data.get("size_arcmin") is not None:
            try:
                size_arcmin = float(data["size_arcmin"])
            except (TypeError, ValueError):
                pass

        options = dict(request.options) if request.options else {}
        if ra_deg is not None and dec_deg is not None:
            try:
                options["ra_deg"] = float(ra_deg)
                options["dec_deg"] = float(dec_deg)
            except (TypeError, ValueError):
                pass
        if band:
            options["band"] = str(band)
        options.setdefault("size_arcmin", size_arcmin)

        target = request.target
        if target is None and name:
            target = Target(name=str(name))

        want_analysis = data.get("want_analysis", False)
        if isinstance(want_analysis, str):
            want_analysis = want_analysis.strip().lower() in ("true", "1", "yes", "si")
        task: TaskType = "morphology_summary" if want_analysis else "fetch_image"

        return AnalyzeRequest(
            request_id=request.request_id,
            message=request.message,
            messages=request.messages,
            target=target,
            task=task,
            image_url=request.image_url,
            options=options,
        )

    def build_prompt(self, request: AnalyzeRequest) -> str:
        """Mantener un helper simple de prompt (útil para debug o futuros usos)."""
        target_name = request.target.name if request.target else "unknown"
        task = request.task or "morphology_summary"
        return (
            "You are a galaxy analysis assistant. "
            f"Task={task}, target={target_name}, "
            f"request_id={request.request_id}."
        )

    def plan_tool_calls(self, request: AnalyzeRequest) -> list[str]:
        """Mapa estático task → tools, útil como guía/documentación."""
        task_to_tools = {
            "segment": ["tool_segment"],
            "measure_basic": ["tool_segment", "tool_measure_basic"],
            "morphology_summary": [
                "tool_segment",
                "tool_measure_basic",
                "tool_morphology_summary",
                "tool_generate_report",
            ],
            "fetch_image": [],
        }
        task = request.task or "morphology_summary"
        return task_to_tools.get(task, task_to_tools["morphology_summary"])

    def generate_accompanying_summary(
        self,
        target_name: str,
        band: str | None,
        morphology_summary: str,
        user_message: str | None = None,
    ) -> str:
        """Responde solo a lo que el usuario pidió: texto conciso que entregue el análisis pedido."""
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key:
            return morphology_summary

        band_info = f" en banda {band}" if band else ""
        user_text = (user_message or "").strip() or f"análisis de {target_name}{band_info}"
        prompt = (
            f"El usuario dijo: «{user_text}».\n\n"
            f"Resultado del análisis: {morphology_summary}\n\n"
            "Responde ÚNICAMENTE a lo que pidió: 1 o 2 frases en español que entreguen ese análisis de forma concisa. "
            "Incluye solo las cifras o detalles que sean relevantes para lo que preguntó. "
            "Sin rodeos, sin añadir lo que no haya pedido."
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "Responde solo con la respuesta concisa al usuario. Nada más."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                content = morphology_summary
            # Siempre indicar la banda en la respuesta para que en el siguiente turno quede claro
            if band and f"en banda {band}" not in content.lower() and "banda " not in content.lower():
                content = f"Análisis de {target_name} en banda {band}. " + content
            return content
        except Exception:
            return morphology_summary

    def generate_image_caption(
        self,
        target_name: str,
        band: str | None,
        user_message: str | None = None,
    ) -> str:
        """Responde solo a lo que el usuario pidió: una frase concisa que entregue exactamente eso."""
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        band_info = f" en banda {band}" if band else ""
        default = f"Aquí tienes la imagen de {target_name}{band_info}."
        if not api_key:
            return default

        user_text = (user_message or "").strip() or f"imagen de {target_name}{band_info}"
        prompt = (
            f"El usuario dijo: «{user_text}».\n\n"
            "Responde ÚNICAMENTE a lo que pidió: una sola frase en español que sea la entrega de eso. "
            "Ejemplo: si pidió 'dame la imagen de M87 en UV', responde 'Aquí tienes la imagen de M87 en UV.' "
            "Solo eso: conciso, sin análisis, sin cifras, sin añadir nada que no haya pedido."
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "Responde solo con la frase de entrega al usuario. Nada más."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                return default
            # Asegurar que la banda figure siempre en el texto (evitar contradicciones en el siguiente turno)
            if band and "banda" not in content.lower() and band.lower() not in content.lower():
                return default
            return content
        except Exception:
            return default
