# Control-Artifact Assurance Spectrum

Every artifact that constrains agent behavior sits somewhere on a spectrum of
assurance — how strongly the artifact guarantees the behavior it describes
actually happens.

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
procedural artifact fixes the steps but still depends on the agent following
them. A machine-validated artifact can be checked against a definition, so a
violation is detectable after the fact. A mechanically enforced artifact
removes the choice: the behavior is executed or blocked by something that is
not a model.

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
name the enforcing one so the reason and the mechanism stay connected.

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
  detectable rather than merely discouraged.
- **Mechanically enforced** — hook scripts such as
  `scripts/protect_main_commit.py` and generated adapters produced by
  `scripts/generate_instruction_adapters.py` take the outcome out of the
  agent's hands entirely. Repository CI is not yet part of this tier.
