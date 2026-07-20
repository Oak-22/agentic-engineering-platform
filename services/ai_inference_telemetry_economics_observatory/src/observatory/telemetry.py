from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class InferenceEvent:
    request_id: str
    timestamp: str
    surface: str
    endpoint: str
    model: str
    latency_ms: float
    status_code: int
    input_tokens: int | None
    output_tokens: int | None

    @classmethod
    def completed(
        cls,
        *,
        request_id: str,
        endpoint: str,
        model: str,
        latency_ms: float,
        status_code: int,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> "InferenceEvent":
        return cls(
            request_id=request_id,
            timestamp=datetime.now(UTC).isoformat(),
            surface="terminal_cli",
            endpoint=endpoint,
            model=model,
            latency_ms=round(latency_ms, 3),
            status_code=status_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class TelemetryEmitter(Protocol):
    def emit(self, event: InferenceEvent) -> None: ...


class NullTelemetryEmitter:
    def emit(self, event: InferenceEvent) -> None:
        return None


class HttpTelemetryEmitter:
    """Best-effort JSON emitter with a deliberately short timeout."""

    def __init__(self, url: str, timeout_seconds: float = 0.1) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds

    def emit(self, event: InferenceEvent) -> None:
        body = json.dumps(asdict(event)).encode("utf-8")
        request = Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds):
            pass


def emit_best_effort(emitter: TelemetryEmitter, event: InferenceEvent) -> None:
    try:
        emitter.emit(event)
    except Exception:
        # Telemetry must never turn into a user-facing inference failure.
        pass
