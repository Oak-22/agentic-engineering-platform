"""Render a Report as one self-contained HTML page.

No CDN, no chart library, no build step: bars are div widths and the whole
page is one file, so it opens from the filesystem with the network off and
keeps working after the tooling that produced it has moved on.

The palette and the light/dark handling are the ones already used by the
committed pages in docs/diagrams/, so a report promoted there by hand sits
beside them without restyling.
"""

from __future__ import annotations

from html import escape

from . import pricing
from .usage_model import UNATTRIBUTED, Report, Rollup

_STYLE = """
:root {
  --paper: #edeeea;
  --paper-raised: #e3e5df;
  --ink: #14181c;
  --ink-soft: #4a5157;
  --rule: #b7bdb9;
  --rule-strong: #8d9598;
  --cool: #0f6e64;
  --cool-fill: #0f6e6420;
  --warm: #a83a2c;
  --warm-fill: #a83a2c20;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #14181a;
    --paper-raised: #1b2022;
    --ink: #ece9e2;
    --ink-soft: #a9b0ac;
    --rule: #3c4345;
    --rule-strong: #565f61;
    --cool: #4fbfae;
    --cool-fill: #4fbfae2b;
    --warm: #e2695a;
    --warm-fill: #e2695a2b;
  }
}

:root[data-theme="dark"] {
  --paper: #14181a;
  --paper-raised: #1b2022;
  --ink: #ece9e2;
  --ink-soft: #a9b0ac;
  --rule: #3c4345;
  --rule-strong: #565f61;
  --cool: #4fbfae;
  --cool-fill: #4fbfae2b;
  --warm: #e2695a;
  --warm-fill: #e2695a2b;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  line-height: 1.55;
}

.sheet { max-width: 980px; margin: 0 auto; padding: 3rem 1.75rem 5rem; }

h1 { font-size: 1.65rem; margin: 0 0 0.35rem; letter-spacing: -0.01em; }
h2 {
  font-size: 1.05rem;
  margin: 2.75rem 0 0.85rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--rule);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
p { margin: 0 0 0.9rem; }
.subtitle { color: var(--ink-soft); margin-bottom: 1.75rem; }

.limits {
  background: var(--paper-raised);
  border: 1px solid var(--rule);
  border-left: 3px solid var(--warm);
  padding: 1rem 1.25rem;
  margin: 0 0 1.5rem;
}
.limits h3 { margin: 0 0 0.5rem; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; }
.limits ul { margin: 0; padding-left: 1.1rem; color: var(--ink-soft); font-size: 0.9rem; }
.limits li { margin-bottom: 0.35rem; }

.tiles { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.5rem; }
.tile {
  flex: 1 1 8.5rem;
  background: var(--paper-raised);
  border: 1px solid var(--rule);
  padding: 0.85rem 1rem;
}
.tile .value { font-size: 1.4rem; font-variant-numeric: tabular-nums; }
.tile .label { color: var(--ink-soft); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }

.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { text-align: right; padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--rule); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--ink-soft); font-weight: 600; font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.04em; }
tbody tr:hover { background: var(--paper-raised); }
td.num { font-variant-numeric: tabular-nums; }
tr.muted td:first-child { color: var(--ink-soft); font-style: italic; }

.bar { position: relative; min-width: 9rem; }
.bar .fill { position: absolute; inset: 0 auto 0 0; background: var(--cool-fill); }
.bar .fill.warm { background: var(--warm-fill); }
.bar span { position: relative; }

footer { margin-top: 3rem; color: var(--ink-soft); font-size: 0.82rem; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88em; }
"""


def _dollars(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.4f}"


def _tokens(value: int) -> str:
    """Abbreviate to three significant figures.

    A dashboard column of raw nine-digit token counts is unreadable, and the
    exact digit is never the question being asked of this table."""
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= limit:
            return f"{value / limit:.2f}{suffix}"
    return str(value)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _tile(value: str, label: str) -> str:
    return (
        f'<div class="tile"><div class="value">{escape(value)}</div>'
        f'<div class="label">{escape(label)}</div></div>'
    )


def _bar_cell(text: str, fraction: float, *, warm: bool = False) -> str:
    """A number with its share of the maximum drawn behind it.

    One cell rather than a separate chart: the comparison is between rows of
    a table that is already there, so a second rendering of the same numbers
    would not add a reading."""
    width = max(0.0, min(1.0, fraction)) * 100
    css_class = "fill warm" if warm else "fill"
    return (
        f'<td class="num bar"><div class="{css_class}" style="width:{width:.1f}%"></div>'
        f"<span>{escape(text)}</span></td>"
    )


def _rollup_rows(rollups: list[Rollup], *, label_unattributed: bool = False) -> str:
    peak_cost = max((r.estimated_cost for r in rollups), default=0.0)
    peak_tokens = max((r.total_tokens for r in rollups), default=0)
    rows = []
    for rollup in rollups:
        muted = label_unattributed and rollup.key == UNATTRIBUTED
        cost = _dollars(rollup.estimated_cost)
        if rollup.unpriced_calls == rollup.calls and rollup.calls:
            cost = "not priced"
        elif rollup.unpriced_calls:
            cost += "+"
        rows.append(
            f'<tr class="{"muted" if muted else ""}">'
            f"<td>{escape(rollup.key)}</td>"
            + _bar_cell(cost, rollup.estimated_cost / peak_cost if peak_cost else 0, warm=muted)
            + _bar_cell(_tokens(rollup.total_tokens), rollup.total_tokens / peak_tokens if peak_tokens else 0, warm=muted)
            + f'<td class="num">{_percent(rollup.cache_read_ratio)}</td>'
            f'<td class="num">{rollup.calls:,}</td>'
            f'<td class="num">{len(rollup.sessions):,}</td>'
            f'<td>{escape(", ".join(sorted(rollup.runtimes)))}</td>'
            "</tr>"
        )
    return "\n".join(rows)


def _table(rollups: list[Rollup], first_column: str, *, label_unattributed: bool = False) -> str:
    return (
        '<div class="scroll"><table><thead><tr>'
        f"<th>{escape(first_column)}</th><th>Est. cost</th><th>Tokens</th>"
        "<th>Cache read</th><th>Calls</th><th>Sessions</th><th>Runtime</th>"
        "</tr></thead><tbody>"
        + _rollup_rows(rollups, label_unattributed=label_unattributed)
        + "</tbody></table></div>"
    )


def _limits(report: Report, sources: str) -> str:
    items = [
        "Cost is <strong>estimated</strong> from published list rates as of "
        f"{escape(pricing.AS_OF)}, multiplied by observed tokens. Nothing here is "
        "billing data: it ignores negotiated rates, subscription plans that bundle "
        "usage, and credits.",
        "Token counts are what each runtime recorded in its own local session "
        "files. They are the runtime's account of the call, not the provider's.",
    ]

    attributed = sum(1 for r in report.by_work_item if r.key != UNATTRIBUTED)
    unattributed = next(
        (r for r in report.by_work_item if r.key == UNATTRIBUTED), None
    )
    if unattributed is not None:
        share = (
            unattributed.estimated_cost / report.total.estimated_cost
            if report.total.estimated_cost
            else 0.0
        )
        items.append(
            f"{_percent(share)} of estimated cost sits on branches that name no work "
            f"item, against {attributed} attributed. Work item totals describe the "
            "attributed minority, not the whole bill."
        )

    if report.unpriced_models:
        items.append(
            "No rate is on file for "
            + ", ".join(f"<code>{escape(m)}</code>" for m in report.unpriced_models)
            + ". Those calls contribute tokens but no cost, so every total they "
            "touch is a floor. Codex records token counts without a model id, so "
            "its spend cannot be priced at all."
        )

    items.append(
        "Quality is absent. This is the cost half of the question; nothing here "
        "says whether the spend produced a good outcome."
    )
    items.append(f"Read from {escape(sources)}.")

    return (
        '<div class="limits"><h3>What this can and cannot show</h3><ul>'
        + "".join(f"<li>{item}</li>" for item in items)
        + "</ul></div>"
    )


def render_report(report: Report, *, generated_at: str, sources: str) -> str:
    """Compose the whole page. Returns HTML text; writes nothing."""
    total = report.total
    window = (
        f"{total.first_seen[:10]} to {total.last_seen[:10]}"
        if total.first_seen and total.last_seen
        else "no dated calls"
    )

    tiles = "".join(
        [
            _tile(_dollars(total.estimated_cost), "Estimated cost"),
            _tile(_tokens(total.total_tokens), "Total tokens"),
            _tile(_percent(total.cache_read_ratio), "Input from cache"),
            _tile(f"{total.calls:,}", "Model calls"),
            _tile(f"{report.session_count:,}", "Sessions"),
            _tile(str(len([r for r in report.by_work_item if r.key != UNATTRIBUTED])), "Work items"),
        ]
    )

    return f"""<title>Inference Cost by Governed Outcome</title>
<style>{_STYLE}</style>
<div class="sheet">
<h1>Inference cost by governed outcome</h1>
<p class="subtitle">{escape(window)} &middot; rendered {escape(generated_at)}</p>

{_limits(report, sources)}

<div class="tiles">{tiles}</div>

<h2>By work item</h2>
<p>What each governed delivery cost, read from the branch each call ran on.
Branches naming no work item are grouped as <em>{UNATTRIBUTED}</em>.</p>
{_table(report.by_work_item, "Work item", label_unattributed=True)}

<h2>By runtime</h2>
<p>The cross-runtime comparison. Token volume is comparable across runtimes;
cost is not, since only one of them records the model that served each call.</p>
{_table(report.by_runtime, "Runtime")}

<h2>By model</h2>
{_table(report.by_model, "Model")}

<h2>By day</h2>
{_table(report.by_day, "Day")}

<footer>
Generated by <code>dashboard-report</code> from local session transcripts.
Rates as of {escape(pricing.AS_OF)}. This file is self-contained and reads
nothing from the network.
</footer>
</div>
"""
