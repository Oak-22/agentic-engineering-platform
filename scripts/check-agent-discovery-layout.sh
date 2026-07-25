#!/bin/sh

set -eu

repository_root=$(git rev-parse --show-toplevel)
cd "$repository_root"

required_paths="
AGENTS.md
.github/copilot-instructions.md
.github/instructions
.agents/skills
"

for required_path in $required_paths; do
  if [ ! -e "$required_path" ]; then
    echo "missing runtime discovery path: $required_path" >&2
    exit 1
  fi
done

if [ -d platform/agent-control-plane/.github ]; then
  echo "nested runtime tree must not exist: platform/agent-control-plane/.github" >&2
  exit 1
fi

for canonical_skill in .github/skills/*; do
  if [ ! -d "$canonical_skill" ]; then
    continue
  fi

  skill_name=$(basename "$canonical_skill")
  skill_file="$canonical_skill/SKILL.md"
  adapter_path=".agents/skills/$skill_name"
  expected_target="../../.github/skills/$skill_name"

  if [ ! -f "$skill_file" ]; then
    echo "canonical skill is missing SKILL.md: $canonical_skill" >&2
    exit 1
  fi

  declared_name=$(sed -n 's/^name:[[:space:]]*["'\'']\{0,1\}\([^"'\'']*\)["'\'']\{0,1\}[[:space:]]*$/\1/p' "$skill_file" | head -n 1)
  if [ "$declared_name" != "$skill_name" ]; then
    echo "skill name does not match directory: $skill_file" >&2
    exit 1
  fi

  if [ ! -L "$adapter_path" ]; then
    echo "missing Codex skill adapter: $adapter_path" >&2
    exit 1
  fi

  if [ "$(readlink "$adapter_path")" != "$expected_target" ]; then
    echo "Codex skill adapter has unexpected target: $adapter_path" >&2
    exit 1
  fi

  if [ ! -f "$adapter_path/SKILL.md" ]; then
    echo "Codex skill adapter does not resolve: $adapter_path" >&2
    exit 1
  fi
done

for adapter_path in .agents/skills/*; do
  if [ ! -e "$adapter_path" ] && [ ! -L "$adapter_path" ]; then
    continue
  fi

  skill_name=$(basename "$adapter_path")
  if [ ! -d ".github/skills/$skill_name" ]; then
    echo "Codex skill adapter has no canonical skill: $adapter_path" >&2
    exit 1
  fi
done

echo "agent discovery layout is rooted correctly"
