from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from .telemetry import InferenceEvent, TelemetryEmitter, emit_best_effort


@dataclass(frozen=True)
class ModelResult:
    content: str
    raw_response: dict[str, Any]
    request_id: str


class InteractionAdapter:
    def __init__(
        self,
        *,
        model_base_url: str,
        model: str,
        api_key: str | None,
        telemetry_emitter: TelemetryEmitter,
        model_timeout_seconds: float = 30.0,
    ) -> None:
        self.model_base_url = model_base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.telemetry_emitter = telemetry_emitter
        self.model_timeout_seconds = model_timeout_seconds

    def ask(self, prompt: str) -> ModelResult:
        request_id = str(uuid.uuid4())
        endpoint = f"{self.model_base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "X-Observatory-Request-ID": request_id,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        with urlopen(request, timeout=self.model_timeout_seconds) as response:
            status_code = response.status
            raw_response = json.load(response)
        latency_ms = (time.perf_counter() - started) * 1000

        usage = raw_response.get("usage", {})
        event = InferenceEvent.completed(
            request_id=request_id,
            endpoint=endpoint,
            model=str(raw_response.get("model", self.model)),
            latency_ms=latency_ms,
            status_code=status_code,
            input_tokens=_optional_int(usage.get("prompt_tokens")),
            output_tokens=_optional_int(usage.get("completion_tokens")),
        )
        emit_best_effort(self.telemetry_emitter, event)

        content = raw_response["choices"][0]["message"]["content"]
        return ModelResult(
            content=content,
            raw_response=raw_response,
            request_id=request_id,
        )


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None
