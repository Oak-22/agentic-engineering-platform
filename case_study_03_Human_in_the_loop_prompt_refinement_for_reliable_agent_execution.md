
Case Study 02 — case_study_02_Human-in-the-Loop_prompt_refinement_for_reliable_agent_execution

Part of: AI-Human Engineering Collaboration — Case Studies & Best Practices

—

Problem

Modern coding agents operate inside repository-scoped environments but often lack the broader architectural reasoning context needed to generate reliable implementation prompts.

This case study documents a workflow where a human operator uses an external reasoning agent to design prompts, which are then executed by repository-scoped coding agents.

The goal is to separate reasoning from execution while maintaining deterministic agent behavior.

—

AI Systems Stack Context

This case study operates at the AgentOps layer of the AI systems stack, which sits downstream of model training and ML operations.

AI Infrastructure / Pre-Training
        ↓
Model Training
        ↓
MLOps
        ↓
LLMOps / AgentOps
        └─ Human-AI Engineering Workflows (this case study)

—

Human-AI Interaction Model

In this workflow, the human acts as the orchestration layer between two AI systems.

Internal Chatbot  ←── Human ──→  External Chatbot

The human iteratively refines prompts through conversation with a reasoning model before passing those prompts to a repository-scoped coding agent.

—

Not To Be Confused With

This model differs from autonomous multi-agent systems where agents communicate directly with each other.Human
|
├── Agent
└── Agent

In this case study, the human remains the coordination layer between agents.

—

Architecture Overview


Two-Tier Agent Architecture
────────────────────────────────────

External Reasoning Layer
(ChatGPT)
        ↓
Prompt Specification
        ↓
Execution Layer
(Repository-scoped agent)
        ↓
Codebase Change


Behavior Persistence Loop
────────────────────────────────────

observe emergent behavior
        ↓
evaluate reliability
        ↓
persist behavior → instruction hierarchy
        ↓
agents operate with updated instructions
        ↓
new interaction patterns emerge
        ↺

—

Investigation Progression

The following examples document the evolution of the workflow as architectural assumptions were tested and refined:

Architecture demonstrated and prompt pipeline validated (Example 1A)
↓
Agent boundary limitation discovered and instruction hierarchy implemented (Example 1B)
↓
Emergent interaction behavior observed and evaluated (Example 1C)

Conceptually, the examples correspond to three layers of the system:

1A — Reasoning / Execution Architecture
Establishes the two-tier agent workflow.

1B — Persistent Instruction Boundary
Defines the structure through which reliable agent behaviors can be formalized and reused.

1C — Emergent Behavior Evaluation and Persistence
Demonstrates how interaction patterns discovered during human–AI collaboration are evaluated and either promoted into persistent instructions or discarded as ephemeral prompts.

———————


Example 1A

Multi-Agent Prompt Chaining with External + Internal Context Model 


This exhibit demonstrates a workflow where an external reasoning agent is used to design prompts that are later executed by repository-scoped coding agents.

Initial prompt development and architectural reasoning occur within ChatGPT Desktop, which maintains long-term conversational context about the operator’s projects, technical trajectory, and working style. This environment supports extended multi-turn interaction with frontier models (e.g., ChatGPT 5.4) and allows architectural reasoning to accumulate across sessions.

Using an out-of-repository reasoning agent provides two key advantages.

First, the reasoning environment maintains persistent cross-project context. Over time, this enables the model to understand the broader domain of a project, its architectural goals, and previously discussed design trade-offs.

Second, separating reasoning from execution improves the reliability of agent behavior. 

The external reasoning agent is used to:

• refine prompts
• structure tasks for deterministic execution
• anticipate failure modes
• decompose complex operations into discrete steps

Once the prompt is sufficiently structured, it is passed to repository-scoped coding agents (such as VS Code Codex or Copilot) that interact directly with the codebase.

The repository execution agent focuses on:

• loading relevant repository context and project structure
• translating the structured prompt into concrete implementation tasks
• generating architecture-consistent code changes
• validating proposed changes against the current codebase state

This results in a two-tier, distributed agent architecture:

Reasoning Layer
External ChatGPT agent used for architectural reasoning and prompt design.

Execution Layer
Repository-scoped coding agents responsible for implementing changes within the codebase.

The workflow therefore separates architectural reasoning from deterministic code execution. The figures that follow illustrate this prompt refinement pipeline in practice.


Figure 1AA — Initial prompt formulation in the external reasoning agent (ChatGPT Desktop — GPT 5.4)

The prompt defines the task for the VS Code Codex agent: proposing code additions that strengthen the user’s Digital Asset Processing Pipeline system despite the primary transformations occurring inside GUI-based tools





Figure 1AB — Prompt refinement and structural expansion in the external reasoning agent

The initial conversational request is iteratively refined into a structured task specification suitable for a repository-scoped coding agent. The refined prompt clarifies architectural context, constraints, and evaluation criteria before being handed off to the VS Code Codex agent for execution.

—

Agent Execution Result

Following prompt refinement (Figure 1B), the structured prompt was handed to the repository-scoped VS Code Codex execution agent.
The agent analyzed the project structure and proposed a set of concrete engineering additions designed to strengthen the system architecture and improve reproducibility, auditability, and pipeline determinism.
Table 1 — Proposed High-Value Code Additions from Execution Agent

Response from GPT-5.4 Codex agent following prompt hand-off from the external reasoning agent.

The agent identified twelve high-value engineering additions that would improve the architectural robustness of the Digital Asset Processing Pipeline.

| Feature | Engineering Pattern | What it would do | Why it strengthens the project | Supports | Difficulty | Portfolio-visible |
|---|---|---|---|---|---|---|
| 1. Dataset manifest generator | System-of-record / Reproducible pipeline input | Scans a batch and emits canonical JSON/YAML manifests for assets, paths, hashes, capture metadata, expected stages, and operator notes | Gives the whole project a concrete system-of-record and makes every run reproducible | All 3 pipeline stages | Medium | High |
| 2. Schema validation layer | Explicit data contracts | Defines Pydantic/JSON Schema models for identity metadata, semantic metadata, normalization plans, mask artifacts, and run outputs | Shows real metadata modeling and boundary enforcement instead of informal conventions | Especially 001 and 003 | Medium | High |
| 3. Preflight CLI | Pre-execution validation / fail-fast pipeline | Checks folder structure, missing sidecars, duplicate filenames, invalid metadata fields, preset compatibility, scene grouping completeness, and unresolved dependencies before a run | Very production-like; proves you thought about failure prevention, not just happy-path execution | All 3 | Medium | High |
| 4. Post-flight verifier | Deterministic stage verification | Verifies expected outputs after GUI work: expected file count, manifest status updates, changed timestamps, sidecar presence, approved stage completion, unresolved exceptions | Makes the GUI step auditable and deterministic after human execution | All 3 | Medium | High |
| 5. Pipeline run ledger | Execution event log / pipeline observability | Stores each run in SQLite with dataset id, stage, operator, timestamps, manifest version, outcomes, exceptions, and approvals | Adds state tracking, traceability, resumability, and audit history | All 3 | Medium | Very high |
| 6. Checkpoint/resume engine | Idempotent stage checkpointing | Marks stage states like planned, ready, in_progress, blocked, review_required, complete, and supports resume from last valid checkpoint | Makes the pipeline feel like a real orchestrated batch system rather than loose scripts | All 3 | Medium | Very high |
| 7. Dry-run / simulation mode | Non-destructive execution preview | Simulates a run without modifying assets; shows what would be validated, what outputs are expected, and where operator intervention is required | Excellent for realism because it explicitly models GUI-bound work as planned/manual checkpoints | All 3 | Low-Medium | High |
| 8. Transformation plan compiler | Executable pipeline planning | Converts dataset metadata plus stage rules into an explicit execution plan: which batch gets which preset, exemplar, mask policy, review gate, and output target | Bridges intent to execution and demonstrates deterministic planning under constraints | Especially 002 and 003 | Medium-High | Very high |
| 9. Dataset integrity checker | Data integrity verification | Detects duplicates via checksums, manifest drift, orphan sidecars, missing raws/exports, broken references, inconsistent scene grouping, and version mismatches | Strong engineering credibility because integrity is central in real batch systems | All 3 | Medium | High |
| 10. Operator review queue | Human-in-the-loop workflow gate | Produces machine-generated review lists for assets needing manual inspection based on failed checks, low-confidence masks, or outlier metadata | Makes manual work first-class and systematic instead of ad hoc | Especially 002 and 003 | Medium | High |
| 11. Structured event logging | Structured observability logging | Emits JSON logs for every stage event, validation result, exception, decision, and checkpoint transition | Lets you build metrics and audit trails cleanly; good systems-engineering signal | All 3 | Low-Medium | Medium-High |
| 12. Metrics/report generator | Pipeline observability & reporting | Produces HTML/Markdown reports summarizing throughput, failure rates, review rates, dataset coverage, stage durations, and defect categories | Gives visible outcomes and makes the project feel operated, measured, and improved over time | All 3 |  |  |


Observations

Several of the proposed additions introduce characteristics typical of production data and batch processing systems, including:
	•	reproducible dataset manifests
	•	schema validation and metadata modeling
	•	deterministic pipeline state tracking
	•	checkpoint and resume capabilities
	•	preflight and post-execution validation

This illustrates how a repository-scoped coding agent, when given sufficiently structured prompts, can propose architectural improvements rather than isolated code fragments.



———————



Example 1B

 Context Boundary Discovery in External Reasoning Agents


During development of the multi-agent workflow described in Example 1A, a limitation of external reasoning agents was observed.

External agents operating outside a code environment lack repository-scale semantic search unless explicitly integrated with a development environment or code indexing system.

As a result, when reasoning about repository structure, an external agent may incorrectly infer relationships between files or documentation layers.

This behavior was discovered while designing a separation between two agent instruction runtime environments.

Two instruction runtime environments are defined:

• Global Agent Runtime Environment
Reusable cross-repository guidance shared across projects.
Implemented in the repository as: .github/agent-instructions/global/

• Repo-Local Agent Runtime Environment
Project-specific constraints, architecture decisions, and operational guidance.
Implemented in the repository as: .github/agent-instructions/repo/

In the screenshot below, the external reasoning agent correctly identified the structure of the Global instruction layer but also incorporated repository-local instructions into the same conceptual scope. This conflation risked weakening the separation between general agent behavior and repository-specific constraints.

The operator then used the external reasoning agent to refine the prompt and explicitly reinforce the intended boundary between the two instruction runtime environments before passing the corrected prompt to the repository-scoped execution agent.





Figure 1BA — External agent misinterprets instruction scope.
The desktop reasoning agent correctly identifies the Global agent instruction layer but also incorporates repository-level instructions into the same conceptual scope. This conflation muddies the intended separation between cross-repository guidance and repository-specific constraints, potentially weakening future agent execution that depends on clear instruction boundaries.





Figure 1BB — Prompt refinement to correct instruction scope.

The operator uses the external reasoning agent to analyze the misinterpretation shown in Figure 1ba. The external agent then refines the prompt to explicitly enforce the intended boundary between Global and Repo-local agent instructions before the task is handed to the repository-scoped execution agent.






Figure 1BC — Corrected instruction hierarchy implemented

The refined prompt successfully establishes a clear separation between Global and repository-local agent instructions. The resulting structure defines a consistent reference hierarchy for agents to follow, preserving reusable cross-project guidance while maintaining repository-specific constraints.

By restoring the intended boundary between instruction scopes, the corrected hierarchy prevents agents from unnecessarily loading unrelated context during execution. This directly addresses the scope conflation observed in Figure 1ba and improves both efficiency and reasoning reliability.


Agent Instruction Hierarchy

General agent instructions
        ↓
Global agent instructions
        ↓
Repository instructions
		

Two orthogonal costs arise when agents load excessive context:

Token Economics
  	- Larger prompts increase inference cost and latency.


Prompt Degradation
		- Irrelevant context reduces signal-to-noise ratio and weakens model reasoning.




————————————





Example 1C

Emergent Interaction Behavior in Human–AI Prompt Loops

After establishing the two-tier reasoning–execution architecture (Example 1A) and correcting the instruction boundary between Global and repository-local agent contexts (Example 1B), an additional interaction pattern became visible during extended use of the system.

In long conversational sessions, the process of debugging or refining agent behavior can itself become part of the model’s future reasoning context. Each corrective explanation, architectural clarification, or prompt refinement persists in the conversation state and may influence how the model behaves in subsequent turns.

This creates a feedback loop in which the act of analyzing model behavior modifies the conditions under which the next behavior is generated. Over time, these interactions can reveal recurring behavioral patterns that developers may choose to formalize into persistent agent instructions.

The following figures illustrate this phenomenon.



Exhibit  1CA — Context Priority Collision as an emergent interaction pattern.

The interaction shown above illustrates a context priority collision, where the model prioritizes attached artifacts over the most recent conversational instruction. This behavior is related to — but distinct from — a second emergent property observed in long conversational sessions: prompt recursion (next image)





Exhibit 1CB — Prompt recursion as an emergent interaction pattern.
Note: Speech-to-text is often used for faster conversational turns. The loose, messy prose in the prompt above illustrates this interaction style. Developers should discern when prompts require precise language and when models can tolerate conversational imprecision (e.g., grammatical errors, filler words, or incomplete technical phrasing). In this example, the prompt captures a spontaneous observation about how emergent interaction patterns appear during extended human–AI collaboration.

In long-horizon human–AI collaboration, each corrective or explanatory turn becomes additional context for future reasoning, producing an iterative chain in which the act of evaluating behavior can itself modify the next behavior under evaluation. 

This dynamic also explains how the instruction hierarchy introduced earlier in Example 1B evolves over time. Behaviors first appear as conversational refinements during human–AI interaction and are later promoted into persistent agent instructions once they prove reliable across sessions.

As a result, the process of documenting or correcting model behavior is not fully external to the system being evaluated. Once a developer explains a failure mode, clarifies intent, or proposes a refinement, that intervention becomes part of the conversational state and can influence subsequent outputs.

When a particular emergent behavior proves useful or reliable, the developer can promote that behavior from ephemeral conversational context to persistent operational guidance. In practice, this is often done by encoding the behavior as a reusable instruction inside a global agent-instruction layer (for example, a global/ instruction file shared across repositories).

Conversely, when a behavior is only relevant to a specific debugging session or experiment, the developer may choose to keep it ephemeral, seeding the behavior through one-off prompts in the reasoning and/or the coding environment without persisting it into the instruction layer.

This creates a practical workflow pattern:

observe emergent behavior
        ↓
evaluate reliability
        ↓
formalize behavior as instruction (global agent layer)
      OR
use behavior temporarily (one-off prompt)

In this way, prompt recursion becomes not just a curiosity of long conversational threads, but a mechanism through which developers iteratively discover, test, and formalize reliable interaction patterns between humans and AI systems





