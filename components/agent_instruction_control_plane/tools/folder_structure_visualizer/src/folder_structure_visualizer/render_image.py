from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

MISSING_MMDC_MESSAGE = (
    "Mermaid CLI not found. Install it with: npm install -g @mermaid-js/mermaid-cli"
)


def render_image(mermaid_file: Path, output_file: Path) -> bool:
    if shutil.which("mmdc") is None:
        print(MISSING_MMDC_MESSAGE)
        return False

    subprocess.run(
        ["mmdc", "-i", str(mermaid_file), "-o", str(output_file)],
        check=True,
    )
    return True
