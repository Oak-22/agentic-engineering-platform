# Closing the GitHub Surface Boundary Drift

## Context

Three surfaces reach GitHub from this repository: git-over-SSH, the hosted
GitHub MCP server, and the `gh` CLI. SSH sits on the Git object layer and
overlaps nothing. The other two are two doors onto the same REST/GraphQL API,
and the repository already routes between them — `github-delivery-mapping.json`
declares `github-mcp` primary and `gh` an optional fallback, and attaches an
`authorizationClass` to each of nineteen operations, so the division is stated
as authority rather than capability.

The MCP surface is preferred because it does strictly less, in a shape a policy
can name. Three places in the current wiring contradict that:

- The `gh` path on this machine authenticates with a classic PAT carrying
  `admin:enterprise`, `admin:org`, `delete_repo`, and fifteen further scopes,
  while the MCP path runs on OAuth consent. Precedence descends from primary to
  fallback while credential scope widens, so degrading to the fallback is also
  an escalation.
- `providers.gh.tools` enumerates eight `gh pr` commands, but
  `workflow-read` names a ninth, `gh run list`, that is absent from that list.
  Nothing detects the divergence: `test_every_mutating_github_operation_keeps_one_semantic_action`
  asserts only that a `fallbackTool` string starts with `gh `.
- `destination-communication-boundaries.md` describes `gh` as a fallback
  without saying that it is the *more capable* interface and is deprioritized
  for that reason, so the ordering reads as a capability ranking.

End state: the fallback is no wider in credential scope than the primary; the
declared `gh` surface cannot silently diverge from the operations that use it,
and is labelled as a declaration rather than an enforced bound; and the
reference states the preference in governance vocabulary, with the condition
under which the trade is weak.

A fourth drift observed alongside these — prose in
`agent-assets/mcp-servers/github/server.md` stating a fourteen-tool surface
against the mapping's seventeen — is already corrected in the working tree;
`server.md:88` reads seventeen and lists the same set as
`providers.github-mcp.tools`. No unit here addresses it.

## How to read this plan

Each unit states **Touches**, **Mechanism**, **Claim**, and **Trace check**.
Every unit is independently reviewable and separately revertible. Unit 2 is the
only one that changes behaviour a check can observe; units 1 and 3 are checked
against machine state and against the mapping respectively.

## Unit 1 — The fallback stops widening authority

**Touches**

- `docs/architecture/destination-communication-boundaries.md`

**Mechanism**

Add a normative scope requirement to the GitHub fallback-order section: the
credential backing the `gh` fallback carries no scope beyond what the
enumerated operations need — `repo` for pull-request operations and
`read:org` where organization membership must resolve — and specifically not
`delete_repo`, `admin:org`, `admin:enterprise`, or `workflow`. State it as a
property the deployment must hold, not as a re-authentication procedure: the
token is machine state, so the current scope set and the command that narrows
it belong in a personal note, not in a reference document that would then decay
on the next rotation. Narrowing the local token is the operator action this
unit authorizes; the repository change is the requirement it is checked
against.

**Claim**

Falling back from the MCP surface to `gh` no longer widens the credential the
operation runs under.

**Trace check**

`gh auth status` lists no scope outside the documented set. Before this unit it
lists twenty-one, including `delete_repo` and `admin:enterprise`. The
falsification: grant the token `delete_repo` again and the same command shows a
scope the reference forbids.

## Unit 2 — The declared `gh` surface cannot silently diverge

**Touches**

- `platform/agent-control-plane/adapters/github/github-delivery-mapping.json`
- `platform/agent-control-plane/tests/test_destination_delivery_contracts.py`
- `platform/agent-control-plane/adapters/github/README.md`

**Mechanism**

Add `gh run list` to `providers.gh.tools`, closing the existing divergence.
Then extend the contract test with a case asserting that every `fallbackTool`
appearing in `operations` is a member of `providers.gh.tools` — a closure
check, alongside the existing prefix assertion rather than replacing it, since
the prefix check still catches a fallback declared against the wrong provider.
The rejected alternative is allowlisting argv patterns to make the enumeration
enforceable at call time: `gh` reaches the agent as one Bash string and
`gh api` bypasses any command-level list, so such an allowlist buys a false
sense of a bound it cannot hold. Instead, state the limitation in the adapter
README: the enumeration declares the intended fallback surface and is checked
for closure against the operations; it does not constrain what `gh` can be
invoked to do.

**Claim**

A `fallbackTool` that is not part of the declared `gh` surface fails a test,
and the enumeration no longer implies an enforcement it does not perform.

**Trace check**

`.venv/bin/python -m unittest discover -s platform/agent-control-plane/tests`
passes. Then delete `"gh run list"` from `providers.gh.tools` and re-run: the
new case fails naming `workflow-read`. Restore it and the suite passes again.

## Unit 3 — The preference is stated as governance, not capability

**Touches**

- `docs/architecture/destination-communication-boundaries.md`

**Mechanism**

Rewrite the fallback-order rationale in the vocabulary the ordering actually
uses. `gh` is the more capable interface — it reaches the whole platform API,
where the MCP surface exposes seventeen typed operations — and is deprioritized
for that reason, because a bounded surface is one a permission gate can name
per operation. Record what the trade costs: the MCP path buys its bound with a
live auth dependency, a hosted-endpoint outage mode, a version GitHub rolls,
and seventeen tool schemas resident in context, so the trade is strong under
unsupervised operation and considerably weaker under supervision. Keep this in
the reference rather than an ADR: it is the standing reason for an ordering the
document already states, not a new decision.

**Claim**

A reader of the fallback order can tell that `gh` is deprioritized for being
less bounded rather than less capable, and can tell when that preference is
weak.

**Trace check**

`grep -n "more capable" docs/architecture/destination-communication-boundaries.md`
returns the rationale sentence, and the surrounding paragraph names both the
unsupervised and supervised cases. Before this unit the grep returns nothing
and the section gives no rationale at all.

## Verification

```sh
gh auth status
.venv/bin/python -m unittest discover -s platform/agent-control-plane/tests
python3 -c "import json,sys; m=json.load(open('platform/agent-control-plane/adapters/github/github-delivery-mapping.json')); d=set(m['providers']['gh']['tools']); u={o['fallbackTool'] for o in m['operations'].values() if 'fallbackTool' in o}; sys.exit(0 if u<=d else 1)"
```

## Risks

- The enumeration in `providers.gh.tools` remains descriptive after unit 2. A
  reader who takes a closure-checked list as an enforced one is making the same
  mistake the unit's README change exists to prevent; the check guards
  consistency, not capability.
- Unit 1's requirement holds only where an operator applies it. Nothing in the
  repository can observe the scope of a token on another machine, so the
  requirement is verifiable at the point of use and not in CI.
- Narrowing the local token removes `workflow`, so any `gh` invocation that
  touches Actions configuration will fail. Reading run status via
  `gh run list` needs only `repo` and is unaffected.
