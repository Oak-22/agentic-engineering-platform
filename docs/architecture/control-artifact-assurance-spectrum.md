# Assurance Spectrum for Control Artifacts

A *control artifact* is any artifact that constrains agent behavior. Each one
sits somewhere on a spectrum of assurance — how strongly the artifact
guarantees the behavior it describes actually happens.

```text
weaker assurance, wider judgment    stronger assurance, narrower judgment
<───────────────────────────────────────────────────────────────────────>

  interpretive   │   procedural   │   machine-validated   │  mechanically
                 │                │                       │  enforced
  instructions,  │   skills,      │   schemas,            │  bounded
  prompts        │   workflows    │   hook definitions    │  scripts, CI
```

## Rule

Assurance strengthens left to right, and so does cost. An interpretive
artifact states intent and depends on a model choosing to honor it. A
procedural artifact orders the steps but still depends on the agent following
them. A machine-validated artifact can be checked against a definition, so a
violation is detectable rather than only discouraged. A synchronous check
that something blocks on also prevents the violation — but that blocking is
mechanical enforcement using the definition as its rule; the tier itself
guarantees only that the check exists, not that anything acts on its result.
A mechanically enforced artifact
removes the choice: the behavior is executed or blocked by something that is
not a model. Its assurance is only as strong as its coverage is complete —
`agent_permission_gate.py` evaluating
`generalist-engineering-agent.policy.json` is a hard gate for every action
its matchers recognize and every runtime whose pre-execution hook fires, and
it strengthens each time a matcher, a policy statement, or the runtime
permission settings it composes with (`.claude/settings.json` and the Codex
and Copilot equivalents) closes another path.

Place a control at the weakest point on the spectrum that its risk tolerates,
and move it rightward when the cost of an unhonored instruction exceeds the
cost of mechanizing it. Do not read the spectrum as a maturity ladder where
everything should end up on the right — expressing judgment, tradeoffs, and
context is exactly what interpretive artifacts are for, and mechanizing that
class of guidance destroys the flexibility that made it useful.

The corollary is that the same requirement can exist at more than one point.
An instruction that says "do not commit to main" and a hook that refuses the
commit are not duplicates: the instruction carries the reason, the hook
carries the guarantee. Where both exist, the interpretive artifact should
name the enforcing one so the reason and the mechanism stay connected. The
*Composition* section below generalizes this from "reason plus guarantee" to
"each tier covers a failure class the others cannot."

## What each tier acts on

The assurance axis is one ordering, but the tiers also differ in *what they
act on*. The two properties co-vary closely, which is why a single spectrum
is enough to place a control; the table records the distinction that
underlies it.

| Assurance tier | Example artifacts | Acts on | Failure mode |
| --- | --- | --- | --- |
| Interpretive | `AGENTS.md`, instructions, prompts | generation of intent — states the reason, depends on the model choosing to honor it | silently ignored by a confused, wrong, or prompt-injected agent |
| Procedural | skills, agent-run workflows | generation of intent — fixes the step order, still depends on the agent executing it | agent deviates from or skips steps |
| Machine-validated | JSON Schemas, asset registries and `validate_asset_registries.py` | the *form* of the artifact — guarantees a left-side output has the shape a right-side enforcer expects; detects malformed controls after the fact | well-formed but wrong-in-substance passes; the post-hoc catch needs a human loop |
| Mechanically enforced | hook scripts (`protect_main_commit.py`, `agent_permission_gate.py`), required deterministic CI checks such as `control-plane-guards` | execution of intent — removes the choice; behavior is run or blocked by something that is not a model | over-broad rule blocks legitimate work; a gap in the matcher lets a bad action through |

Two cases do not sit cleanly in a row:

- **A model-based gate borrows the enforcement position without its
  assurance.** The Claude Code auto-mode classifier runs at the enforcement
  point — an execution-time gate, evaluated after the static deny and ask
  rules — but it is a model, so it carries interpretive-grade assurance:
  fallible, and itself subject to prompt injection. This is why the
  mechanically enforced tier assumes the enforcer is *not* a model, and why
  static deny rules are always evaluated before any such classifier.
- **Machine-validation also feeds leftward.** A schema documents the
  expected shape, so it shapes how the interpretive and procedural author
  writes the artifact in the first place. Teaching the left and gating for
  the right is what makes this tier read as a bridge between authored intent
  and mechanical consumption rather than a point on the line.

## Composition

The spectrum places one control. Composition is the separate question of why
a requirement is worth stating at more than one tier, and the answer is not
redundancy: the tiers fail on non-overlapping classes.

- Interpretive and procedural artifacts fail when the agent is confused,
  wrong, or prompt-injected.
- Machine-validated artifacts fail when a well-formed artifact is wrong in
  substance.
- Mechanically enforced artifacts fail when a matcher misses a variant, or
  when no statement enumerates the action at all.

No one tier's failure set contains another's, so stacking tiers adds
coverage rather than reinforcing a single point.

One asymmetry is load-bearing. The mechanically enforced tier acts by
enumeration — a recognized action or condition resolves to a decision and
everything else gets no opinion, whether the enforcer is the permission
gate's matcher, a hook keyed on the checked-out branch, or a CI script
checking the properties it was written to check — so the set it governs is
closed by construction. The
interpretive tier acts by generalization: a stated principle applies to
situations no one enumerated. That gives the left side weak but non-zero
purchase on a failure class the right side structurally cannot reach: the
open-ended tail of novel actions, new tools, and paths no policy statement
anticipated. This is the concrete reason the spectrum is not a maturity
ladder — mechanizing the interpretive layer away removes the only control
with any reach into the unenumerated.

### Prompt injection

Prompt injection is the cross-cutting attack on this arrangement. It targets
the interpretive tier specifically — the tier holding the tail — by placing
attacker-controlled text where the agent reads it as context: an issue body,
a review comment, a fetched page, an MCP tool result, a file in the repo. It
does not enter through authentication. A fully authenticated user running a
legitimate task on a fully authorized agent still carries injected
instructions into the context window when the content the agent reads
contains them, and reading that content is often the task itself.

The boundary that matters against injection is data provenance — which
tokens came from a trusted instruction source versus untrusted content read
as subject matter — not identity. Because the interpretive tier cannot be
made injection-proof, the mechanically enforced tier is what limits a
successful injection: a scoped policy, human-approval tiers, and global
immutable denies limit what a planted instruction can turn into — a merged
pull request, rewritten history — along the paths the gate recognizes and
the refs the ruleset protects. Containment, not prevention, and containment
only within that coverage.

Instruction provenance is a partial control with two layers that are easy to
conflate. A per-prompt instruction reference that is completely faithful
establishes which instruction sources governed that turn. It does not cover
text that entered the context as subject matter — an issue body, a tool
result, a source file — so it cannot rule out an injected instruction there,
and it does not prove that the referenced instructions were not themselves
mutated: altering `AGENTS.md` or an instruction file in a way that survives
review is a separate attack surface, addressed by source-control review,
pinned or signed assets, and registry validation, not by the manifest.

### Trust postures

Guidance and containment are two points on a longer progression, where each
step removes one assumption the platform makes about the agent.

1. **Trust intent, execution, and report.** The agent is told the rule and
   trusted to follow it and to describe what it did. Every interpretive and
   procedural artifact operates here.
2. **Stop trusting execution.** A pre-execution gate evaluates the action
   itself and denies, asks, or allows regardless of what the agent intended.
   `agent_permission_gate.py` is this step — containment, not persuasion.
3. **Stop trusting the report.** "The agent says it followed the lifecycle"
   is not evidence. An observer the agent cannot author — a hook-seeded
   evidence record, an independent review, CI — establishes what happened.
   The instruction manifest is an early, narrow instrument here: its
   hook-seeded ledger line records which instruction sources loaded, not
   what the agent did with them, and it audits rather than intercepts.

The steps are additive, not sequential replacements. Step 1's guidance stays
because it is the only layer with reach into the unenumerated tail. Step 2's
containment stays because a model's reasoning cannot be fully verified, so a
residual of untrusted cooperation always remains — which is why containment
carries more weight than verification: on the paths the gate recognizes and
the refs the ruleset protects, an unfaithful agent still cannot merge a pull
request or rewrite history. Outside that coverage the runtime's own
permission flow and the destination's controls are what remain.

## Existing instances

- **Interpretive** — `AGENTS.md` and the instructions under
  `platform/agent-control-plane/agent-assets/instructions/` state working
  rules and response contracts that each runtime's model applies by judgment.
- **Procedural** — skill packages under `agent-assets/skills/` fix the step
  order for governed delivery, Atlassian operations, and Git workflow, but
  the agent still executes them.
- **Machine-validated** — the JSON Schemas under
  `platform/agent-control-plane/contracts/` and the asset registries checked
  by `scripts/validate_asset_registries.py` make malformed control artifacts
  detectable rather than merely discouraged. `agent-permission-policy.schema.json`
  validates the *shape* of `generalist-engineering-agent.policy.json`; the
  gate below enforces its *content*.
- **Mechanically enforced** — hook scripts take the outcome out of the
  agent's hands within their stated coverage. `scripts/protect_main_commit.py`
  blocks ordinary commits on checked-out `main`, on clones that opt into
  `.githooks` and absent the explicit `AEP_ALLOW_MAIN_COMMIT=1` bypass: a
  local, bypassable guard. The generalist agent identity lives here: its
  boundary is the `generalist-engineering-agent.policy.json` document, and
  `scripts/agent_permission_gate.py`, registered as a pre-execution hook,
  resolves a matched action and resource pair to deny, human approval, or
  affirmative allow — human approval rendered as `ask` on Claude Code and
  GitHub Copilot and as a deny with reason on Codex, whose `ask` fails open
  — while a pair no statement addresses falls through to the runtime's own
  permission handling. The policy document is the boundary; the gate is the
  mechanism carrying the guarantee, bounded by matcher coverage and by which
  runtimes fire the hook. Repository CI belongs to this tier for merges to
  `main`: the `protect-main` ruleset requires the `control-plane-guards` and
  `aep-copilot-review` status checks, so a failing check blocks the merge
  regardless of what any agent reports. The first is deterministic; the
  second is a non-model ruleset enforcing a model-derived signal, which
  [ADR-0006](adr/0006-treat-copilot-review-as-contextual-corroboration.md)
  treats as contextual corroboration rather than independent verification.
