# Agent Asset Discovery Layers

This diagram separates lightweight repository entrypoints / runtime-native
installation surfaces from provider translation and canonical agent assets.

```mermaid
flowchart TB
    subgraph E["LIGHT — REPOSITORY ENTRYPOINTS"]
        direction TB
        ES[" "]

        subgraph ER[" "]
            direction LR
            A["AGENTS.md<br/>Shared entrypoint"]
            C["CLAUDE.md<br/>Claude entrypoint"]
            G[".github/copilot-instructions.md<br/>Copilot entrypoint"]
        end
    end

    subgraph D["LIGHT — RUNTIME-NATIVE INSTALLATION SURFACES"]
        direction TB
        DS[" "]

        subgraph DR[" "]
            direction LR
            DO[".agents/skills/<br/>Codex skill discovery"]
            CO[".codex/<br/>Codex config + hooks"]
            DC[".claude/<br/>Claude discovery"]
            DG["agent-related .github/<br/>Copilot discovery"]
        end
    end

    RT["platform/agent-control-plane/<br/>adapters/runtimes/<br/>capability mappings + renderers"]

    subgraph S["HEAVY — SHARED REPOSITORY ASSETS"]
        direction TB
        SS[" "]
        ROOT["platform/agent-control-plane/<br/>agent-assets/"]

        subgraph SR[" "]
            direction LR
            I["instructions/"]
            K["skills/"]
            H["hooks/"]
            P["execution-policies/"]
            R["role-charters/"]
        end
    end

    A --> DO
    CO --> ROOT
    C --> DC
    G --> DG

    DO --> ROOT
    DC --> ROOT
    DG --> ROOT

    ROOT --> RT
    RT -.-> DO
    RT -.-> CO
    RT -.-> DC
    RT -.-> DG

    ROOT --> I
    ROOT --> K
    ROOT --> H
    ROOT --> P
    ROOT --> R

    style ES fill:transparent,stroke:transparent
    style DS fill:transparent,stroke:transparent
    style SS fill:transparent,stroke:transparent

    style ER fill:transparent,stroke:transparent
    style DR fill:transparent,stroke:transparent
    style SR fill:transparent,stroke:transparent
```
