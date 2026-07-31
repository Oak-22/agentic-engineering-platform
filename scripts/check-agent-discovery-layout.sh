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
platform/agent-control-plane/agent-assets/role-charters
platform/agent-control-plane/scripts/instruction_manifest_hook.py
platform/agent-control-plane/scripts/provider_docs_session_start.py
"

for required_path in $required_paths; do
  if [ ! -e "$required_path" ]; then
    echo "missing runtime discovery path: $required_path" >&2
    exit 1
  fi
done

python3 -m json.tool .codex/hooks.json >/dev/null
python3 -m json.tool .claude/settings.json >/dev/null

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

for canonical_skill in .agents/skills/*; do
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

  for runtime in .claude .github; do
    adapter_path="$runtime/skills/$skill_name"
    expected_target="../../.agents/skills/$skill_name"

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

for runtime in .claude .github; do
  for adapter_path in "$runtime"/skills/*; do
    if [ ! -e "$adapter_path" ] && [ ! -L "$adapter_path" ]; then
      continue
    fi

    skill_name=$(basename "$adapter_path")
    if [ "$skill_name" = "README.md" ]; then
      continue
    fi

    if [ ! -d ".agents/skills/$skill_name" ]; then
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
workflow_target="../../.agents/skills/manage-git-workflow/references/git-foundations.md"
if [ ! -L "$workflow_adapter" ] || [ "$(readlink "$workflow_adapter")" != "$workflow_target" ]; then
  echo "workflow adapter has unexpected target: $workflow_adapter" >&2
  exit 1
fi

if ! grep -q '^@AGENTS.md$' CLAUDE.md; then
  echo "CLAUDE.md must import AGENTS.md" >&2
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
