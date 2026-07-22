from __future__ import annotations

import json
import io
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from unittest.mock import patch

from observatory.adapter import InteractionAdapter
from observatory.cli import main
from observatory.telemetry import HttpTelemetryEmitter


class _FixtureHandler(BaseHTTPRequestHandler):
    telemetry_events: list[dict[str, Any]] = []

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))

        if self.path == "/v1/chat/completions":
            assert body["messages"][0]["content"] == "hello observatory"
            response = {
                "model": "mock-model",
                "choices": [{"message": {"role": "assistant", "content": "mock reply"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }
            self._json_response(200, response)
            return

        if self.path == "/telemetry":
            self.telemetry_events.append(body)
            self._json_response(202, {"accepted": True})
            return

        self._json_response(404, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _json_response(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class AdapterFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _FixtureHandler.telemetry_events = []
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self) -> None:
        _FixtureHandler.telemetry_events.clear()

    def test_returns_model_response_and_emits_valid_telemetry(self) -> None:
        adapter = InteractionAdapter(
            model_base_url=self.base_url,
            model="mock-model",
            api_key=None,
            telemetry_emitter=HttpTelemetryEmitter(f"{self.base_url}/telemetry"),
        )

        result = adapter.ask("hello observatory")

        self.assertEqual(result.content, "mock reply")
        self.assertEqual(len(_FixtureHandler.telemetry_events), 1)
        event = _FixtureHandler.telemetry_events[0]
        self.assertEqual(event["request_id"], result.request_id)
        self.assertEqual(event["surface"], "terminal_cli")
        self.assertEqual(event["model"], "mock-model")
        self.assertEqual(event["status_code"], 200)
        self.assertEqual(event["input_tokens"], 3)
        self.assertEqual(event["output_tokens"], 2)
        self.assertGreaterEqual(event["latency_ms"], 0)

    def test_telemetry_failure_does_not_break_model_response(self) -> None:
        adapter = InteractionAdapter(
            model_base_url=self.base_url,
            model="mock-model",
            api_key=None,
            telemetry_emitter=HttpTelemetryEmitter(
                "http://127.0.0.1:1/telemetry",
                timeout_seconds=0.01,
            ),
        )

        result = adapter.ask("hello observatory")

        self.assertEqual(result.content, "mock reply")

    def test_cli_prints_the_model_response(self) -> None:
        output = io.StringIO()
        environment = {
            "MODEL_BASE_URL": self.base_url,
            "MODEL_NAME": "mock-model",
            "TELEMETRY_URL": f"{self.base_url}/telemetry",
        }

        with (
            patch.dict("os.environ", environment, clear=True),
            patch("sys.argv", ["observatory", "hello observatory"]),
            redirect_stdout(output),
        ):
            main()

        self.assertEqual(output.getvalue(), "mock reply\n")
        self.assertEqual(len(_FixtureHandler.telemetry_events), 1)


if __name__ == "__main__":
    unittest.main()
