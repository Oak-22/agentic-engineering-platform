from __future__ import annotations

from html import escape
from pathlib import Path


def render_html_viewer(svg_file: Path, title: str) -> str:
    svg = svg_file.read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #101214;
      --panel: #181c20;
      --text: #f4f7fb;
      --muted: #aab4c0;
      --line: #2b333b;
      --accent: #6bb7ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      height: 100vh;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .toolbar {{
      position: fixed;
      z-index: 2;
      top: 16px;
      left: 16px;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: color-mix(in srgb, var(--panel) 92%, transparent);
      box-shadow: 0 12px 32px rgb(0 0 0 / 0.24);
    }}
    button {{
      min-width: 40px;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #222932;
      color: var(--text);
      font: inherit;
      cursor: pointer;
    }}
    button:hover {{ border-color: var(--accent); }}
    .zoom-readout {{
      min-width: 62px;
      color: var(--muted);
      text-align: center;
      font-variant-numeric: tabular-nums;
    }}
    .canvas {{
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      cursor: grab;
      background:
        linear-gradient(90deg, rgb(255 255 255 / 0.04) 1px, transparent 1px),
        linear-gradient(rgb(255 255 255 / 0.04) 1px, transparent 1px),
        var(--bg);
      background-size: 32px 32px;
    }}
    .canvas.dragging {{ cursor: grabbing; }}
    .stage {{
      transform-origin: 0 0;
      width: max-content;
      height: max-content;
    }}
    .stage svg {{
      display: block;
      max-width: none !important;
      background: white;
      box-shadow: 0 20px 70px rgb(0 0 0 / 0.36);
    }}
  </style>
</head>
<body>
  <div class="toolbar" aria-label="Graph controls">
    <button type="button" data-action="zoom-out" title="Zoom out">-</button>
    <button type="button" data-action="zoom-in" title="Zoom in">+</button>
    <button type="button" data-action="fit" title="Fit to screen">Fit</button>
    <button type="button" data-action="reset" title="Reset view">Reset</button>
    <span class="zoom-readout" aria-live="polite">100%</span>
  </div>
  <main class="canvas" aria-label="Interactive folder graph">
    <div class="stage">
{svg}
    </div>
  </main>
  <script>
    const canvas = document.querySelector(".canvas");
    const stage = document.querySelector(".stage");
    const svg = stage.querySelector("svg");
    const readout = document.querySelector(".zoom-readout");
    let scale = 1;
    let x = 0;
    let y = 0;
    let dragStart = null;

    function graphBox() {{
      const viewBox = svg.viewBox.baseVal;
      if (viewBox && viewBox.width && viewBox.height) {{
        return {{ width: viewBox.width, height: viewBox.height }};
      }}
      const rect = svg.getBoundingClientRect();
      return {{ width: rect.width || 1000, height: rect.height || 1000 }};
    }}

    function lockSvgSize() {{
      const box = graphBox();
      svg.style.width = `${{box.width}}px`;
      svg.style.height = `${{box.height}}px`;
    }}

    function applyTransform() {{
      stage.style.transform = `translate(${{x}}px, ${{y}}px) scale(${{scale}})`;
      readout.textContent = `${{Math.round(scale * 100)}}%`;
    }}

    function zoomAt(nextScale, originX, originY) {{
      const clamped = Math.min(5, Math.max(0.1, nextScale));
      x = originX - ((originX - x) / scale) * clamped;
      y = originY - ((originY - y) / scale) * clamped;
      scale = clamped;
      applyTransform();
    }}

    function fitToScreen() {{
      const box = graphBox();
      const padding = 72;
      const nextScale = Math.min(
        (canvas.clientWidth - padding) / box.width,
        (canvas.clientHeight - padding) / box.height
      );
      scale = Math.min(1.5, Math.max(0.1, nextScale));
      x = (canvas.clientWidth - box.width * scale) / 2;
      y = (canvas.clientHeight - box.height * scale) / 2;
      applyTransform();
    }}

    document.querySelector("[data-action='zoom-in']").addEventListener("click", () => {{
      zoomAt(scale * 1.2, canvas.clientWidth / 2, canvas.clientHeight / 2);
    }});
    document.querySelector("[data-action='zoom-out']").addEventListener("click", () => {{
      zoomAt(scale / 1.2, canvas.clientWidth / 2, canvas.clientHeight / 2);
    }});
    document.querySelector("[data-action='fit']").addEventListener("click", fitToScreen);
    document.querySelector("[data-action='reset']").addEventListener("click", () => {{
      scale = 1;
      x = 24;
      y = 72;
      applyTransform();
    }});
    canvas.addEventListener("wheel", (event) => {{
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.08 : 1 / 1.08;
      zoomAt(scale * factor, event.clientX, event.clientY);
    }}, {{ passive: false }});
    canvas.addEventListener("pointerdown", (event) => {{
      dragStart = {{ pointerX: event.clientX, pointerY: event.clientY, x, y }};
      canvas.classList.add("dragging");
      canvas.setPointerCapture(event.pointerId);
    }});
    canvas.addEventListener("pointermove", (event) => {{
      if (!dragStart) return;
      x = dragStart.x + event.clientX - dragStart.pointerX;
      y = dragStart.y + event.clientY - dragStart.pointerY;
      applyTransform();
    }});
    canvas.addEventListener("pointerup", () => {{
      dragStart = null;
      canvas.classList.remove("dragging");
    }});
    window.addEventListener("resize", fitToScreen);
    lockSvgSize();
    fitToScreen();
  </script>
</body>
</html>
"""
