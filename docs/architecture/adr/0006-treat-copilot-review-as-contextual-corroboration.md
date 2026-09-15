---
title: Treat Copilot review as contextual corroboration
summary: Decline to build a reviewer isolation boundary; keep Copilot review repository-aware, name the self-graded-exam gap it leaves, and state what would reopen the question.
adr: ADR-0006
status: accepted
date: 2026-09-14
scope: platform
affected_components:
  - platform/agent-control-plane
  - .github
related_jira:
  - AEPI-149
related_confluence: []
supersedes: []
---

# Treat Copilot review as contextual corroboration

## Context

The ordered Copilot review gate gives every pull request to `main` an
external review the producing agent cannot grant itself. That is an authority
property: ADR-0005 keeps acceptance with a human, and the gate keeps the
review outside the agent's credential. It is not a statistical-independence
property. Copilot code review reads repository instructions, agent
instructions, and skills from the pull request's head branch, so producer and
reviewer share context and can share blind spots. GitHub's
[Copilot code review documentation](https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/copilot-code-review)
states the head-branch behavior (checked 2026-09-15).

A captured proposal asked whether AEP should build a verification-independent
reviewer: pinned policy, a blind or minimally contextual reviewer, a separate
tool plane, provider diversity. A business would take that on for one of two
reasons — a security-posture requirement, or evidence that shared context is
degrading review quality. Neither holds here. The repository has one
maintainer with write access, so no adversarial producer exists; and no
defect attributable to instruction context has been observed reaching
`main`. Meanwhile the contextual reading is where Copilot's value comes from:
it knows the adapter layout, the skill packaging, and the ADRs, and a
context-free reviewer would trade that precision for generic findings.

One concrete gap survives the analysis. Because Copilot reads instructions
from the head branch, a pull request that changes an instruction surface
alongside code is reviewed under criteria the same change wrote. The
producer does not alter Copilot; it alters a file Copilot trusts, in the one
place Copilot reads it before anyone has approved it. In a single-maintainer
repository this is never an attack. It is a self-graded exam: the realistic
case is an agent adjusting an instruction file mid-task, after which the
Copilot result on that pull request means less than usual.

## Decision

AEP does not build a reviewer isolation boundary. Copilot code review stays
repository-aware and is described as **contextual corroboration**: an
external review the agent cannot grant itself, which improves the odds of
catching a defect but does not constitute independent verification.

User-facing readiness, trace output, and documentation use that term. The
phrase "independent verification" is reserved for a reviewer whose policy,
state, credentials, and tool surfaces are separately bounded and negatively
verified, which this repository does not have.

The self-graded-exam gap is addressed by visibility, not isolation. A pull
request that touches any instruction surface Copilot reads is one where the
Copilot result does not stand in for the human's own reading of the change.
Those surfaces are the runtime adapters and everything they resolve to:

```text
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
.github/instructions/**
.github/skills/**
platform/agent-control-plane/agent-assets/instructions/**
platform/agent-control-plane/agent-assets/skills/**
```

The canonical trees are in the list because the `.github/` files are thin
adapters; a change to a canonical instruction reaches Copilot without any
`.github/` path appearing in the diff. Recursive patterns keep the guard
tracking the directories rather than a snapshot of their depth.

## Consequences

- No new reviewer infrastructure, policy pinning, or provider migration is
  scheduled for this concern.
- `copilot-review-gate.md` and any readiness output describe the gate as
  contextual corroboration and link this record instead of an open proposal.
- A path-scoped signal — a ruleset target, a required check, or a label — is
  the delivery unit that makes the self-graded-exam case visible on the pull
  request. Until it lands, the human reviewer applies the path list by hand.
- Custom instructions steer Copilot's emphasis; they do not disable its
  baseline review. A pull request can lower the bar for its own review, not
  remove it, which is why visibility is proportionate.
- The decision rests on stated premises. It is valid only while the reopen
  conditions below are all false.

## Reopen when

Any one of these is sufficient to open a superseding record:

- A second identity gains write access to the repository, or agent-authored
  pull requests are accepted without a human reading the diff.
- A defect that Copilot review should have caught reaches `main`, and the
  miss is attributable to instruction context rather than model capability.
- GitHub changes where Copilot code review reads instructions from — for
  example, from the base branch or a pinned policy ref — which would remove
  the gap without AEP building anything.
- A compliance or customer requirement demands demonstrably independent
  review rather than external review.

## Alternatives considered

- **Trusted-policy review** (instructions sourced from a pinned base-branch
  revision). Rejected for now: GitHub does not offer it natively, so it would
  require AEP to run its own review harness, and the premise it defends
  against — a producer that would rewrite policy — does not exist here.
- **Blind or minimally contextual reviewer.** Rejected: it discards the
  repository knowledge that makes current findings precise, and the
  false-positive cost lands on every pull request to defend against a threat
  that has not been observed.
- **Copilot cloud agent as delegated reviewer.** Rejected: moving from code
  review to an agent with implementation capability widens authority rather
  than narrowing it, and does not change where instructions are read from.
- **Differential verification** (deterministic validators alongside Copilot).
  Not rejected — `control-plane-guards` already plays this role for
  structural checks — but it is not a substitute for reviewer independence
  and is not extended on the basis of this concern.
