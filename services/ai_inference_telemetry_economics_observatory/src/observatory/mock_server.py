from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class MockModelHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._json_response(404, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = json.loads(self.rfile.read(content_length))
        prompt = request_body["messages"][-1]["content"]
        model = request_body.get("model", "mock-model")
        response = {
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"mock reply: {prompt}",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": _word_count(prompt),
                "completion_tokens": _word_count(f"mock reply: {prompt}"),
            },
        }
        self._json_response(200, response)

    def log_message(self, format: str, *args: object) -> None:
        return None

    def _json_response(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), MockModelHandler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="observatory-mock",
        description="Run a local OpenAI-compatible mock model endpoint.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = create_server(args.host, args.port)
    print(
        f"Mock model listening at http://{args.host}:{server.server_port}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _word_count(value: str) -> int:
    return len(value.split())


if __name__ == "__main__":
    main()
