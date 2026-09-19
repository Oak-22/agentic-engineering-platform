# Assertion-to-Evidence Ledger

<!-- generated from ledger.json by platform/agent-control-plane/scripts/render_assertion_ledger.py; edit the JSON, then re-run the script -->

## Column key

| Column | Values |
| --- | --- |
| Confirmed | A human's label on the finding's quality: **green** — holds as stated; **yellow** — holds with a caveat noted in the row; **red** — does not hold. A row enters as **unlabelled** and stays so until a human reads it. |
| Found by | Who judged the assertion unsupported: **human**, or `<runtime>:<session>` (the same session ID the commit trailer carries). **unrecorded** — the judging session was not captured. |
| Direction | **never** — the evidence was never produced. **expired** — it existed and stopped being true. **undetermined** — not yet established which. |
| Countermeasure that should have caught it | The mechanism that, if operating, would have surfaced the instance before a human did. **none** — no such mechanism exists; the instance is a current gap. |
| Caught? | **yes** — the countermeasure surfaced it. **no** — a human found it first; the row says how. |
| Fixed | What was done, or **open** with a pointer to where it is tracked. |

## Instances

| # | Confirmed | Found | Found by | Where | Asserted | Actual | Direction | Countermeasure that should have caught it | Caught? | Fixed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | unlabelled | 2026-09-14 | claude:2130d90a | `future/governed-delivery-cardinality-latency-adr.md:54` (since deleted) | "Trace check — validate the ADR frontmatter" | No ADR frontmatter validator has ever existed in the repository | never | traceable-change plan template — falsifiable units | no — form complied with, rule not applied | file deleted 2026-09-14; validator judged not worth building |
| 2 | unlabelled | 2026-09-14 | claude:2130d90a | `README.md:23-25` and `docs/diagrams/agentic-engineering-platform-diagram.svg` | "Telemetry findings and validated learning feed back into the Agent Control Plane" | No artifact names a return mechanism; the diagram draws the return arcs dotted; the actual path is a maintainer editing an instruction by PR | never | none — no mechanism checks prose against diagram | no — surfaced by an outside reader's six questions | outcome B landed 2026-09-19 (AEPI-165, PR #113): `README.md` prose and diagram caption now name the maintainer-by-PR path and state the automated path is not built; `future/close-the-feedback-loop.md` retains outcome A only |
| 3 | unlabelled | 2026-09-14 | claude:2130d90a | `platform/agent-control-plane/agent-assets/skills/shape-readme-entrypoint/SKILL.md:19` | Routes content to `docs/product-thesis.md` | File does not exist at repository or component root | undetermined | check_links.py (machine-local) — external checker outside this repository | yes — on first run; the tool postdates the instance by weeks | open |
| 4 | unlabelled | 2026-08-30 (recorded 2026-09-14) | unrecorded | Atlassian connector `createIssueLink` tool description (vendor artifact) | `inwardIssue` is the blocking or duplicating side | Inverted relative to Jira; six links created reversed, no connector-side deletion | never | none — tool descriptions are consumed at face value | no — found when the links were inspected in Jira | TODO recorded in `manage-jira-confluence/SKILL.md`; links removed by hand |
| 5 | unlabelled | 2026-09-14 | claude:2130d90a | `future/` as a directory | Each file: "delete when the work lands" | Six files added 2026-08-06 → 2026-09-05; zero deletions in git history before 2026-09-14 | expired | decay-rate convention / future/ deletion rule — `artifact-formatting.md` | no — the rule had no enforcement and no reader | four files deleted, one promoted to ADR-0006, on 2026-09-14 |

## Tallies

Computed from the instances above by the renderer.

| Countermeasure | Instances it should have caught | Caught | Missed |
| --- | --- | --- | --- |
| traceable-change plan template | 1 | 0 | 1 |
| decay-rate convention / future/ deletion rule | 1 | 0 | 1 |
| check_links.py (machine-local) | 1 | 1 | 0 |
| prompt-instruction manifest evidence labels | 0 | n/a | n/a |
| negative verification (ADR-0005) | 0 | n/a | n/a |
| no countermeasure exists | 2 | n/a | n/a |

By direction: never 3, expired 1, undetermined 1.

## Reading the tallies

Five instances, four found in one session and one recorded retrospectively from an earlier observation, is enough to state the mechanism and not enough to state a rate. Countermeasures with zero instances have not been exercised, not shown to work. Instances with no countermeasure are the current gaps.
