#!/bin/sh

set -eu

repository_root=$(git rev-parse --show-toplevel)
cd "$repository_root"

required_paths="
AGENTS.md
CLAUDE.md
.github/copilot-instructions.md
.codex/hooks.json
.claude/settings.json
.github/instructions
.github/skills
.agents/skills
.agents/skills/README.md
.codex/hooks/README.md
.claude/rules
.claude/skills
.claude/skills/README.md
.claude/hooks/README.md
platform/agent-control-plane/agent-assets/instructions
platform/agent-control-plane/agent-assets/hooks
platform/agent-control-plane/agent-assets/execution-policies
platform/agent-control-plane/agent-assets/role-charters
platform/agent-control-plane/agent-assets/skills
platform/agent-control-plane/adapters/runtimes
platform/agent-control-plane/adapters/runtimes/codex/README.md
platform/agent-control-plane/adapters/runtimes/codex/generated-projections.txt
platform/agent-control-plane/adapters/runtimes/claude/README.md
platform/agent-control-plane/adapters/runtimes/claude/generated-projections.txt
platform/agent-control-plane/adapters/runtimes/github-copilot/README.md
platform/agent-control-plane/adapters/runtimes/github-copilot/generated-projections.txt
platform/agent-control-plane/scripts/instruction_manifest_hook.py
platform/agent-control-plane/scripts/provider_docs_session_start.py
platform/agent-control-plane/scripts/validate_asset_registries.py
platform/agent-control-plane/agent-assets/hooks/hooks_registry.json
platform/agent-control-plane/agent-assets/skills/skills_registry.json
platform/agent-control-plane/agent-assets/instructions/instructions_registry.json
"

for required_path in $required_paths; do
  if [ ! -e "$required_path" ]; then
    echo "missing runtime discovery path: $required_path" >&2
    exit 1
  fi
done

python3 -m json.tool .codex/hooks.json >/dev/null
python3 -m json.tool .claude/settings.json >/dev/null
validation_python=platform/agent-control-plane/.venv/bin/python
if [ ! -x "$validation_python" ]; then
  validation_python=python3
fi
"$validation_python" platform/agent-control-plane/scripts/validate_asset_registries.py

if ! grep -q '"SessionStart"' .claude/settings.json \
  || ! grep -q '"InstructionsLoaded"' .claude/settings.json \
  || ! grep -q '"UserPromptSubmit"' .claude/settings.json \
  || ! grep -q '"SessionStart"' .codex/hooks.json \
  || ! grep -q '"UserPromptSubmit"' .codex/hooks.json; then
  echo "prompt instruction manifest hooks are incomplete" >&2
  exit 1
fi

if [ -d platform/agent-control-plane/.github ]; then
  echo "nested runtime tree must not exist: platform/agent-control-plane/.github" >&2
  exit 1
fi

# Runtime-native paths are installation surfaces, not alternate canonical
# stores. Every checked-in file in these surfaces must be a discovery link, a
# canonical instruction import, or an explicitly approved native config or
# documentation file. Additions require an intentional allowlist change.
native_surface_roots="
.agents
.codex
.claude
.github/agents
.github/hooks
.github/instructions
.github/prompts
.github/skills
"

generated_projection_manifests="
platform/agent-control-plane/adapters/runtimes/codex/generated-projections.txt
platform/agent-control-plane/adapters/runtimes/claude/generated-projections.txt
platform/agent-control-plane/adapters/runtimes/github-copilot/generated-projections.txt
"

for generated_projection_manifest in $generated_projection_manifests; do
  while IFS= read -r generated_projection; do
    case "$generated_projection" in
      ""|\#*)
        continue
        ;;
    esac

    case "$generated_projection_manifest:$generated_projection" in
      *runtimes/codex/generated-projections.txt:.agents/* \
        |*runtimes/codex/generated-projections.txt:.codex/* \
        |*runtimes/claude/generated-projections.txt:.claude/* \
        |*runtimes/github-copilot/generated-projections.txt:.github/agents/* \
        |*runtimes/github-copilot/generated-projections.txt:.github/hooks/* \
        |*runtimes/github-copilot/generated-projections.txt:.github/instructions/* \
        |*runtimes/github-copilot/generated-projections.txt:.github/prompts/* \
        |*runtimes/github-copilot/generated-projections.txt:.github/skills/*)
        ;;
      *)
        echo "generated projection is outside its runtime-native surface: $generated_projection" >&2
        exit 1
        ;;
    esac

    if [ ! -e "$generated_projection" ] && [ ! -L "$generated_projection" ]; then
      echo "declared generated projection is missing: $generated_projection" >&2
      exit 1
    fi
  done < "$generated_projection_manifest"
done

is_declared_generated_projection() {
  projection_path=$1

  for projection_manifest in $generated_projection_manifests; do
    if grep -Fqx "$projection_path" "$projection_manifest"; then
      return 0
    fi
  done

  return 1
}

for native_surface_root in $native_surface_roots; do
  find "$native_surface_root" \( -type f -o -type l \) -print
done | while IFS= read -r native_path; do
  case "$native_path" in
    .agents/skills/README.md \
      |.codex/README.md \
      |.codex/config.toml \
      |.codex/hooks.json \
      |.codex/hooks/README.md \
      |.claude/README.md \
      |.claude/settings.json \
      |.claude/settings.local.json \
      |.claude/hooks/README.md \
      |.claude/skills/README.md \
      |.github/agents/README.md \
      |.github/hooks/README.md \
      |.github/prompts/README.md \
      |.github/skills/README.md)
      ;;
    .agents/skills/*|.claude/skills/*|.github/prompts/*|.github/skills/*)
      if [ ! -L "$native_path" ]; then
        echo "runtime discovery projection must be a symlink: $native_path" >&2
        exit 1
      fi
      ;;
    .claude/rules/*.md|.github/instructions/*.instructions.md)
      # Canonical imports are resolved and validated below.
      ;;
    *)
      if ! is_declared_generated_projection "$native_path"; then
        echo "unclassified runtime-native installation file: $native_path" >&2
        exit 1
      fi
      ;;
  esac
done

canonical_skills_dir="platform/agent-control-plane/agent-assets/skills"
runtime_skill_dirs=".agents/skills .claude/skills .github/skills"

for canonical_skill in "$canonical_skills_dir"/*; do
  if [ ! -d "$canonical_skill" ]; then
    continue
  fi

  skill_name=$(basename "$canonical_skill")
  skill_file="$canonical_skill/SKILL.md"

  if [ ! -f "$skill_file" ]; then
    echo "canonical skill is missing SKILL.md: $canonical_skill" >&2
    exit 1
  fi

  declared_name=$(sed -n 's/^name:[[:space:]]*["'\'']\{0,1\}\([^"'\'']*\)["'\'']\{0,1\}[[:space:]]*$/\1/p' "$skill_file" | head -n 1)
  if [ "$declared_name" != "$skill_name" ]; then
    echo "skill name does not match directory: $skill_file" >&2
    exit 1
  fi

  for runtime_skills_dir in $runtime_skill_dirs; do
    adapter_path="$runtime_skills_dir/$skill_name"
    expected_target="../../platform/agent-control-plane/agent-assets/skills/$skill_name"

    if [ ! -L "$adapter_path" ]; then
      echo "missing skill adapter: $adapter_path" >&2
      exit 1
    fi

    if [ "$(readlink "$adapter_path")" != "$expected_target" ]; then
      echo "skill adapter has unexpected target: $adapter_path" >&2
      exit 1
    fi

    if [ ! -f "$adapter_path/SKILL.md" ]; then
      echo "skill adapter does not resolve: $adapter_path" >&2
      exit 1
    fi
  done
done

for runtime_skills_dir in $runtime_skill_dirs; do
  for adapter_path in "$runtime_skills_dir"/*; do
    if [ ! -e "$adapter_path" ] && [ ! -L "$adapter_path" ]; then
      continue
    fi

    skill_name=$(basename "$adapter_path")
    if [ "$skill_name" = "README.md" ]; then
      continue
    fi

    if [ ! -d "$canonical_skills_dir/$skill_name" ]; then
      echo "skill adapter has no canonical skill: $adapter_path" >&2
      exit 1
    fi
  done
done

for adapter_path in .github/instructions/*.instructions.md .claude/rules/*.md; do
  import_path=$(sed -n 's/^@//p' "$adapter_path" | head -n 1)
  if [ -z "$import_path" ]; then
    echo "instruction adapter is missing a canonical import: $adapter_path" >&2
    exit 1
  fi

  adapter_directory=$(dirname "$adapter_path")
  if ! (cd "$adapter_directory" && test -f "$import_path"); then
    echo "instruction adapter import does not resolve: $adapter_path" >&2
    exit 1
  fi
done

workflow_adapter=".github/prompts/git-foundations.prompt.md"
workflow_target="../../platform/agent-control-plane/agent-assets/skills/manage-git-workflow/references/git-foundations.md"
if [ ! -L "$workflow_adapter" ] || [ "$(readlink "$workflow_adapter")" != "$workflow_target" ]; then
  echo "workflow adapter has unexpected target: $workflow_adapter" >&2
  exit 1
fi

if ! grep -q '^@AGENTS.md$' CLAUDE.md \
  || ! grep -q '^@AGENTS.md$' .github/copilot-instructions.md; then
  echo "runtime entrypoints must import AGENTS.md" >&2
  exit 1
fi

for entrypoint in AGENTS.md CLAUDE.md .github/copilot-instructions.md; do
  line_count=$(wc -l < "$entrypoint")
  if [ "$line_count" -gt 100 ]; then
    echo "runtime entrypoint exceeds 100 lines: $entrypoint" >&2
    exit 1
  fi
done

echo "agent discovery layout and canonical adapters are valid"
