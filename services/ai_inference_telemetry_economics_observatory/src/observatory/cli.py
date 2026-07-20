from __future__ import annotations

import argparse
import os

from .adapter import InteractionAdapter
from .telemetry import HttpTelemetryEmitter, NullTelemetryEmitter



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="observatory")
    parser.add_argument("prompt", help="Prompt to send to the configured model")
    return parser



def main() -> None:
    args = build_parser().parse_args()
    telemetry_url = os.getenv("TELEMETRY_URL")
    emitter = (
        HttpTelemetryEmitter(telemetry_url)
        if telemetry_url
        else NullTelemetryEmitter()
    )
    adapter = InteractionAdapter(
        model_base_url=os.getenv("MODEL_BASE_URL", "http://127.0.0.1:8080"),
        model=os.getenv("MODEL_NAME", "test-model"),
        api_key=os.getenv("MODEL_API_KEY"),
        telemetry_emitter=emitter,
    )
    print(adapter.ask(args.prompt).content)


if __name__ == "__main__":
    main()
