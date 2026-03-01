from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.config import settings


class AIClientError(Exception):
    pass


class AIClient:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self._model = settings.openai_model
        self._last_used_model: str | None = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def configured_model(self) -> str:
        return self._model

    @property
    def last_used_model(self) -> str | None:
        return self._last_used_model

    def ask_for_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self._client:
            raise AIClientError("OPENAI_API_KEY ni nastavljen.")

        try:
            response = self._request_with_fallback(system_prompt, user_prompt)
        except Exception as exc:
            msg = str(exc)
            if "insufficient_quota" in msg or "exceeded your current quota" in msg.lower():
                raise AIClientError(
                    "Presezena API kvota. Preveri plan, billing in limite na OpenAI platformi."
                ) from exc
            raise AIClientError(f"Napaka pri klicu AI storitve: {msg}") from exc

        text_output = (response.output_text or "").strip()
        if not text_output:
            raise AIClientError("AI model ni vrnil vsebine. Poskusi znova ali preveri kvoto/model.")

        normalized = self._extract_json_text(text_output)
        try:
            return json.loads(normalized)
        except json.JSONDecodeError as exc:
            snippet = normalized[:200].replace("\n", " ")
            raise AIClientError(f"AI je vrnil neveljaven JSON. Izhod: {snippet}") from exc

    def _request_with_fallback(self, system_prompt: str, user_prompt: str):
        payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return self._create_response(self._model, payload)
        except Exception as exc:
            msg = str(exc).lower()
            # If configured model is unavailable, fallback to stable high-quality model.
            should_fallback = (
                "model_not_found" in msg
                or ("model" in msg and ("not found" in msg or "does not exist" in msg or "must be verified" in msg))
            )
            if self._model != "gpt-4.1" and should_fallback:
                return self._create_response("gpt-4.1", payload)
            raise

    def _create_response(self, model: str, payload: list[dict[str, str]]):
        try:
            response = self._client.responses.create(
                model=model,
                input=payload,
                temperature=0.3,
            )
            self._last_used_model = model
            return response
        except Exception as exc:
            msg = str(exc).lower()
            # Some models (e.g., gpt-5) do not support temperature.
            if "unsupported parameter" in msg and "temperature" in msg:
                response = self._client.responses.create(
                    model=model,
                    input=payload,
                )
                self._last_used_model = model
                return response
            raise

    def _extract_json_text(self, text: str) -> str:
        # Accept plain JSON or markdown fenced JSON, and salvage first {...} block.
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1].strip()
        return text.strip()
