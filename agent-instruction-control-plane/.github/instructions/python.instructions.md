---
description: "Portable Python code standards"
applyTo: "**/*.py"
---
# Python Guidance

## Version Contract

Use the Python version declared by the repository first.

## Design Principles

- Favor clarity over cleverness.
- Keep pure transformation logic separate from I/O orchestration.
- Use typed contracts where they improve API clarity.
- Make failure modes explicit with actionable errors.

## Verification

Match verification effort to risk and report checks that could not be
run.
