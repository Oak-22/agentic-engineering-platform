# Canonical Hooks

This directory owns provider-neutral hook definitions and portable resources
that implement Agent Control Plane lifecycle behavior. Add a hook package only
when a concrete lifecycle action exists.

A canonical hook definition describes lifecycle intent, its command or
resource, timeout and context expectations, and failure behavior. Provider
event names, configuration syntax, supported versions, and renderers belong in
[`../../adapters/runtimes/`](../../adapters/runtimes/).

Keep general control-plane executables in [`../../scripts/`](../../scripts/).
Colocate a script here only when it is an intrinsic, portable resource of one
hook package. Hooks support lifecycle automation and observation; they do not
replace sandboxing, managed execution policy, CI, IAM, or other enforcement
boundaries.
