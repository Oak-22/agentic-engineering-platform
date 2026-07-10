# MVP: CLI Interaction Adapter

## 1. Prove the adapter

```text
CLI prompt → interaction adapter → mock model API
                     └→ test telemetry collector
```

- Mock API returns a fixed response and token usage.
- CLI receives that response unchanged.
- Test collector receives one valid telemetry event.
- With the collector unavailable, the CLI response still succeeds.

## 2. Build the telemetry path

```text
local daemon → PostgreSQL → SQL assertion
```

## 3. Connect them

```text
CLI prompt → interaction adapter → mock/model API
                     └→ local daemon → PostgreSQL → SQL assertion
```
