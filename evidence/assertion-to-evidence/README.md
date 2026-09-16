# Assertion-to-evidence ledger

Dated instances where a repository artifact asserted more than had been
shown, recorded against the countermeasure that should have caught it. The
argument this ledger supports is in
[`platform/agent-control-plane/docs/strategy/assertion-to-evidence.md`](../../platform/agent-control-plane/docs/strategy/assertion-to-evidence.md);
that note carries one status line derived from this ledger and nothing else
that decays.

[`ledger.json`](ledger.json) is the source of truth; [`ledger.md`](ledger.md)
is rendered from it and never hand-edited. To add or label an instance, edit
the JSON — one key per line, so a label change is a one-line edit — then run:

```sh
python platform/agent-control-plane/scripts/render_assertion_ledger.py
```

CI runs the same script with `--check` and fails if the render is stale, so
the tallies can never disagree with the rows. The schema is
[`contracts/assertion-ledger.schema.json`](../../platform/agent-control-plane/contracts/assertion-ledger.schema.json).

Add a row when an instance is found. Do not remove rows when the instance is
fixed; record the fix in the row.

- [`ledger.json`](ledger.json) — the instances, source of truth.
- [`ledger.md`](ledger.md) — rendered view with computed tallies.
