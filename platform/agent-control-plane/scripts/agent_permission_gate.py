#!/usr/bin/env python3
"""Evaluate one PreToolUse event against IAM-style agent permission policies.

Run with `--hook --runtime <claude|codex>` to answer one PreToolUse event
from stdin. Denies or asks per the deny-overrides evaluation order in
AEPI-92: global immutable denies first (never overridable), then the
resolved principal's policy document (Deny beats Allow), then silence for
everything a matched principal did not address or that this gate has no
opinion on at all. `ask` is Claude Code-only; Codex substitutes a deny
carrying the same reason, because Codex's `ask` fails open.

The command matcher is a regex over raw command text, not parsed argv, and
shares the false-positive/evasion limitation `governed_task_preflight.py`
documents for the same reason: hardening it against deliberate evasion is a
separate, later change.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

PERMISSIONS_DIR = Path(__file__).resolve().parent.parent / "agent-assets" / "execution-policies" / "permissions"
DEFAULT_AGENT_TYPE = "generalist-engineering-agent"
REPO_NAME = "agentic-engineering-platform"

# Claude Code's built-in Task-tool subagent_type values do not yet map to
# Agent Registry agent types one-to-one (see AGENTS.md's note that role
# charters are "reference or translation from runtime-specific subagent
# definitions," not a shared schema). Until that mapping exists, only a
# runtime agent_type present in this table resolves to a specialist policy;
# everything else, including no agent_type at all, resolves to the default
# principal. This is a known limitation, not an oversight.
AGENT_TYPE_ALIASES: dict[str, str] = {}

GIT_PUSH_PATTERN = re.compile(r"\bgit\s+push\b")
GIT_PUSH_FORCE_PATTERN = re.compile(r"\bgit\s+push\b[^|;&\n]*(?:--force-with-lease\b|--force\b|(?<!\S)-f(?!\S))")
GIT_PUSH_DELETE_PATTERN = re.compile(r"\bgit\s+push\b[^|;&\n]*--delete\b")
GIT_PUSH_BRANCH_ARG_PATTERN = re.compile(
    r"\bgit\s+push\b(?:\s+(?:--force-with-lease|--force|-f|-u|--set-upstream))*\s+(?:[\w.\-/]+)\s+([\w.\-/]+)"
)
GIT_COMMIT_PATTERN = re.compile(r"\bgit\s+commit\b")
GIT_COMMIT_NO_VERIFY_PATTERN = re.compile(r"\bgit\s+commit\b[^|;&\n]*--no-verify\b")
GIT_BRANCH_DELETE_PATTERN = re.compile(r"\bgit\s+branch\s+(?:-d|-D|--delete)\b")
GH_PR_CREATE_PATTERN = re.compile(r"\bgh\s+pr\s+create\b")
GH_PR_MERGE_PATTERN = re.compile(r"\bgh\s+pr\s+merge\b")

MAIN_BRANCH_NAMES = frozenset({"main", "master"})


class ActionMatch:
    """One recognized action, ready for global-deny and policy evaluation."""

    def __init__(self, action: str, resource: str) -> None:
        self.action = action
        self.resource = resource


def repository_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return Path(result.stdout.strip())


def current_branch(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def pushed_branch(command: str, root: Path) -> str:
    """Best-effort target branch for a `git push` command, for the resource string.

    Falls back to the current branch when the command does not name one
    explicitly (a bare `git push` on a tracking branch), and to `*` when
    even that cannot be determined.
    """
    match = GIT_PUSH_BRANCH_ARG_PATTERN.search(command)
    if match:
        return match.group(1)
    branch = current_branch(root)
    return branch if branch else "*"


def global_deny_reason(command: str, root: Path) -> str | None:
    """The four action classes no principal, including the default, may Allow."""
    if GIT_PUSH_FORCE_PATTERN.search(command):
        return (
            "git push --force (or -f / --force-with-lease) is a global deny: "
            "force-pushing rewrites history on a published ref, and no policy "
            "may authorize it."
        )
    if GIT_COMMIT_NO_VERIFY_PATTERN.search(command):
        return "git commit --no-verify is a global deny: bypassing commit hooks is never legal regardless of authority."
    if GIT_COMMIT_PATTERN.search(command):
        branch = current_branch(root)
        if branch in MAIN_BRANCH_NAMES:
            return f"Direct commit on '{branch}' is a global deny regardless of authority."
    return None


def recognize_action(command: str, root: Path) -> ActionMatch | None:
    """Classify a command into a namespaced action + resource, or None (no opinion)."""
    if GIT_PUSH_DELETE_PATTERN.search(command):
        return ActionMatch("git:branch:delete", f"git:{REPO_NAME}:branch/*")
    if GIT_PUSH_PATTERN.search(command):
        branch = pushed_branch(command, root)
        return ActionMatch("git:push", f"git:{REPO_NAME}:branch/{branch}")
    if GIT_BRANCH_DELETE_PATTERN.search(command):
        return ActionMatch("git:branch:delete", f"git:{REPO_NAME}:branch/*")
    if GH_PR_MERGE_PATTERN.search(command):
        return ActionMatch("gh:pr:merge", f"git:{REPO_NAME}:*")
    if GH_PR_CREATE_PATTERN.search(command):
        return ActionMatch("gh:pr:create", f"git:{REPO_NAME}:*")
    return None


def resolve_agent_type(event: dict) -> str:
    raw = event.get("agent_type")
    if not raw:
        return DEFAULT_AGENT_TYPE
    return AGENT_TYPE_ALIASES.get(str(raw), DEFAULT_AGENT_TYPE)


def load_policy(agent_type: str) -> dict | None:
    path = PERMISSIONS_DIR / f"{agent_type}.policy.json"
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def resource_matches(patterns: Sequence[str], resource: str) -> bool:
    return any(fnmatch.fnmatchcase(resource, pattern) for pattern in patterns)


def evaluate_policy(policy: dict, match: ActionMatch) -> str | None:
    """Return 'Deny', 'AllowApproval', 'Allow', or None (statement did not address this action).

    Deny beats Allow within one policy document, matching IAM deny-overrides
    semantics: every statement is checked, and any matching Deny wins even
    if an earlier or later statement would Allow the same action.
    """
    verdict: str | None = None
    for statement in policy.get("statements", []):
        if match.action not in statement.get("action", []):
            continue
        if not resource_matches(statement.get("resource", []), match.resource):
            continue
        if statement.get("effect") == "Deny":
            return "Deny"
        if verdict is None:
            condition = statement.get("condition") or {}
            verdict = "AllowApproval" if condition.get("requiresHumanApproval") else "Allow"
    return verdict


def deny_decision(reason: str) -> dict:
    """The PreToolUse JSON shape both Claude Code and Codex accept for deny."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def ask_decision(reason: str) -> dict:
    """Claude Code-only: routes to the runtime's permission prompt."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }


def hook_response(tool_input: dict, event: dict, root: Path, runtime: str) -> dict | None:
    command = str(tool_input.get("command", ""))
    if not command:
        return None

    reason = global_deny_reason(command, root)
    if reason is not None:
        return deny_decision(reason)

    match = recognize_action(command, root)
    if match is None:
        return None

    agent_type = resolve_agent_type(event)
    policy = load_policy(agent_type)
    if policy is None:
        return None

    verdict = evaluate_policy(policy, match)
    if verdict == "Deny":
        return deny_decision(
            f"Denied by policy {policy.get('policyId', agent_type)}: "
            f"{agent_type} may not perform {match.action} on {match.resource}."
        )
    if verdict == "AllowApproval":
        reason = (
            f"{match.action} on {match.resource} requires human approval "
            f"under policy {policy.get('policyId', agent_type)}."
        )
        if runtime == "codex":
            # ask fails open on Codex: it marks the hook run failed and
            # continues the tool call, which is worse than no gate at all.
            return deny_decision(reason)
        return ask_decision(reason)
    # verdict is "Allow" or None (unaddressed by this principal's policy):
    # fall through silently to the existing tier-based default in
    # governed-repository-change.md.
    return None


def run_as_hook(stdin_payload: str, cwd: Path, runtime: str) -> int:
    """Read one PreToolUse event from stdin and print a decision, if any.

    Silent (prints nothing, exits 0) for malformed input, a non-Bash tool
    call, a command outside a Git worktree, or any command this gate has no
    opinion on. The JSON on stdout decides the outcome for a matched,
    gated command; exit code carries no meaning in this mode.
    """
    try:
        event = json.loads(stdin_payload)
    except json.JSONDecodeError:
        return 0

    tool_name = event.get("tool_name")
    if tool_name is not None and tool_name != "Bash":
        return 0

    root = repository_root(cwd)
    if root is None:
        return 0

    decision = hook_response(event.get("tool_input") or {}, event, root, runtime)
    if decision is not None:
        print(json.dumps(decision))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--hook" not in args:
        print("agent_permission_gate.py only supports --hook mode.", file=sys.stderr)
        return 2

    runtime = "claude"
    if "--runtime" in args:
        index = args.index("--runtime")
        if index + 1 < len(args):
            runtime = args[index + 1]

    return run_as_hook(sys.stdin.read(), Path.cwd(), runtime)


if __name__ == "__main__":
    raise SystemExit(main())
