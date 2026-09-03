# Human-AI Engineering Collaboration Case Studies

This directory preserves evidence from real human-AI engineering workflows.
Each case study records an obstacle, the investigation, the collaboration
dynamic, and the resulting lesson.

## Purpose

Use these records to understand observed failure modes, prompt refinement,
instruction-system evolution, and the boundary between human judgment and
agent execution. They inform platform changes but do not define runtime
requirements.

## Related Platform Component

For reusable instructions, runtime adapters, skills, hooks, provenance,
and workflow scaffolding, see the platform's
[`agent control plane`](../../platform/agent-control-plane/).

## Case Studies

1. [EC2 SSM registration in a private VPC](case_study_01_ssm_registration.md)
2. [Prompt-to-instruction provenance and recursive refinement](case_study_02_instruction_provenance_feedback_loop.md)
3. [Human-in-the-loop prompt refinement](case_study_03_Human_in_the_loop_prompt_refinement_for_reliable_agent_execution.md)
4. [Agent-control plane convergence](case_study_04_agent_control_plane_convergence.md)

Supporting visual explanations:

- [Filename propagation reasoning trace](filename-propagation-reasoning-trace.md)
- [Git fetch explainer](git-fetch-explainer-diagram.md)

## Repository Policy

These records are governed by the monorepo's root [license](../../LICENSE) and
repository guidance.
