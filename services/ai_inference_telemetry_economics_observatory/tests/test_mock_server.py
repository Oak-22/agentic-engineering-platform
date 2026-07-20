from __future__ import annotations

import os
import subprocess
import sys
import threading
import unittest

from observatory.mock_server import create_server


class MockServerIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server("127.0.0.1", 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_cli_process_calls_standalone_mock_contract(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "MODEL_BASE_URL": self.base_url,
                "MODEL_NAME": "mock-model",
                "PYTHONPATH": "src",
            }
        )

        result = subprocess.run(
            [sys.executable, "-m", "observatory.cli", "hello"],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "mock reply: hello\n")


if __name__ == "__main__":
    unittest.main()
