#!/usr/bin/env python3
"""Evaluate one PreToolUse event against IAM-style agent permission policies.

Run with `--hook --runtime <claude|codex|copilot>` to answer one PreToolUse
event from stdin. Denies or asks per the deny-overrides evaluation order in
AEPI-92: global immutable denies first (never overridable), then the
resolved principal's policy document (Deny beats Allow), then silence for
everything a matched principal did not address or that this gate has no
opinion on at all.

`ask` behavior and the emitted JSON shape both differ by runtime (AEPI-94):

- Claude Code: response wrapped in `hookSpecificOutput`; `ask` routes to the
  human permission prompt.
- Codex: same wrapper; `ask` fails open (Codex marks the hook run failed and
  continues the tool call), so this gate substitutes a `deny` carrying the
  same reason instead of ever emitting `ask` there.
- GitHub Copilot: response is NOT wrapped — `{"permissionDecision": ...}` is
  written directly to stdout. `ask` is safe to emit as-is; Copilot's own
  cloud-agent runtime downgrades `ask` to `deny` itself when no human is
  available, so this gate does not need to pre-empt it the way it does for
  Codex. Whether Copilot's PreToolUse hooks actually fire for subagent tool
  calls at all is unverified as of AEPI-94 (see the Jira ticket) — this gate
  emits a correctly-shaped decision either way, but that is not the same
  claim as "Copilot enforcement works."

The command matcher is a regex over raw command text, not parsed argv, and
shares the false-positive/evasion limitation `governed_task_preflight.py`
documents for the same reason: hardening it against deliberate evasion is a
separate, later change. MCP tool names are matched against the explicit
GitHub and Jira mutation maps below.
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

# AEPI-94 gave every Developer Agent Group specialist a translated subagent
# file per runtime (.claude/agents/, .codex/agents/, .github/agents/), each
# setting its native identity field to the exact Agent Registry slug. So a
# real specialist call's `agent_type` now equals a policy filename directly
# (see resolve_agent_type) — no alias needed for those. This table exists
# only to explicitly, fail-safely map each runtime's *built-in fallback*
# identity — used when no custom subagent was named — to the default
# principal, rather than leaving that mapping implicit. An agent_type absent
# from both this table and the known-policy set still resolves to
# DEFAULT_AGENT_TYPE (see resolve_agent_type); it never default-permits.
AGENT_TYPE_ALIASES: dict[str, str] = {
    # Claude Code built-in subagent_type fallbacks
    "general-purpose": DEFAULT_AGENT_TYPE,
    "Explore": DEFAULT_AGENT_TYPE,
    "Plan": DEFAULT_AGENT_TYPE,
    "claude": DEFAULT_AGENT_TYPE,
    "statusline-setup": DEFAULT_AGENT_TYPE,
    "claude-code-guide": DEFAULT_AGENT_TYPE,
    # Codex built-in agent fallbacks
    "default": DEFAULT_AGENT_TYPE,
    "worker": DEFAULT_AGENT_TYPE,
    "explorer": DEFAULT_AGENT_TYPE,
}

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

GITHUB_MCP_ACTIONS = {
    "create_pull_request": "github:pull_request:create",
    "update_pull_request": "github:pull_request:update",
    "pull_request_review_write": "github:pull_request:review",
    "merge_pull_request": "github:pull_request:merge",
}
JIRA_MCP_ACTIONS = {
    "createjiraissue": "jira:issue:create",
    "editjiraissue": "jira:issue:update",
    "transitionjiraissue": "jira:issue:transition",
    "createissuelink": "jira:issue:link",
}

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
        return ActionMatch("github:pull_request:merge", f"github:{REPO_NAME}:*")
    if GH_PR_CREATE_PATTERN.search(command):
        return ActionMatch("github:pull_request:create", f"github:{REPO_NAME}:*")
    return None


def is_github_mcp_tool(tool_name: object) -> bool:
    """Return whether a runtime tool name addresses the configured GitHub MCP."""
    if not isinstance(tool_name, str):
        return False
    lowered = tool_name.lower()
    return "github" in lowered and lowered.rsplit("__", 1)[-1] in GITHUB_MCP_ACTIONS


def is_jira_mcp_tool(tool_name: object) -> bool:
    """Return whether a runtime tool name addresses a Jira MCP surface."""
    if not isinstance(tool_name, str):
        return False
    lowered = re.sub(r"[^a-z0-9]", "", tool_name.lower())
    return ("jira" in lowered or "atlassian" in lowered) and any(
        lowered.endswith(operation) for operation in JIRA_MCP_ACTIONS
    )


def is_governed_mcp_tool(tool_name: object) -> bool:
    return is_github_mcp_tool(tool_name) or is_jira_mcp_tool(tool_name)


def recognize_mcp_action(tool_name: object, tool_input: dict) -> ActionMatch | None:
    """Map destination MCP mutations onto a semantic action namespace."""
    if is_github_mcp_tool(tool_name):
        operation = str(tool_name).lower().rsplit("__", 1)[-1]
        action = GITHUB_MCP_ACTIONS[operation]
        repository = tool_input.get("repository")
        if isinstance(repository, dict):
            owner = repository.get("owner")
            name = repository.get("name") or repository.get("repo")
            repository = f"{owner}/{name}" if owner and name else None
        elif not isinstance(repository, str):
            owner = tool_input.get("owner")
            name = tool_input.get("repo") or tool_input.get("name")
            repository = f"{owner}/{name}" if owner and name else None
        resource = f"github:{repository}:*" if repository else f"github:{REPO_NAME}:*"
        return ActionMatch(action, resource)

    if is_jira_mcp_tool(tool_name):
        normalized = re.sub(r"[^a-z0-9]", "", str(tool_name).lower())
        operation = next(
            operation for operation in JIRA_MCP_ACTIONS if normalized.endswith(operation)
        )
        action = JIRA_MCP_ACTIONS[operation]
        issue_key = (
            tool_input.get("issueIdOrKey")
            or tool_input.get("issueKey")
            or tool_input.get("issue_key")
        )
        project_key = tool_input.get("projectKey") or tool_input.get("project_key")
        project = str(project_key or "*")
        issue = str(issue_key or "*")
        return ActionMatch(action, f"jira:{project}:issue/{issue}")
    return None


def resolve_agent_type(event: dict) -> str:
    raw = event.get("agent_type")
    if not raw:
        return DEFAULT_AGENT_TYPE
    raw = str(raw)
    if load_policy(raw) is not None:
        # A registered Agent Registry slug with its own policy document —
        # a translated subagent file (.claude/agents/, .codex/agents/,
        # .github/agents/) set its native identity field to this exact
        # string (AEPI-94). Identity passthrough, no alias needed.
        return raw
    return AGENT_TYPE_ALIASES.get(raw, DEFAULT_AGENT_TYPE)


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


def _decision(runtime: str, permission_decision: str, reason: str) -> dict:
    """Emit the correct JSON shape for the runtime: wrapped for Claude Code
    and Codex, unwrapped for GitHub Copilot (AEPI-94)."""
    payload = {
        "permissionDecision": permission_decision,
        "permissionDecisionReason": reason,
    }
    if runtime == "copilot":
        return payload
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", **payload}}


def deny_decision(reason: str, runtime: str = "claude") -> dict:
    """The PreToolUse JSON shape each supported runtime accepts for deny."""
    return _decision(runtime, "deny", reason)


def ask_decision(reason: str, runtime: str = "claude") -> dict:
    """Claude Code and Copilot: routes to a human decision (Copilot's own
    runtime downgrades this to deny under the cloud agent when no human is
    available). Never call this for Codex — its `ask` fails open."""
    return _decision(runtime, "ask", reason)


def hook_response(
    tool_input: dict,
    event: dict,
    root: Path,
    runtime: str,
    tool_name: object = "Bash",
) -> dict | None:
    mcp_match = recognize_mcp_action(tool_name, tool_input)
    if mcp_match is not None:
        match = mcp_match
        command = ""
    elif tool_name not in (None, "Bash") and runtime != "copilot":
        return None
    else:
        match = None
        command = str(tool_input.get("command", ""))
    if mcp_match is None and not command:
        return None

    if mcp_match is None:
        reason = global_deny_reason(command, root)
        if reason is not None:
            return deny_decision(reason, runtime)

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
            f"{agent_type} may not perform {match.action} on {match.resource}.",
            runtime,
        )
    if verdict == "AllowApproval":
        reason = (
            f"{match.action} on {match.resource} requires human approval "
            f"under policy {policy.get('policyId', agent_type)}."
        )
        if runtime == "codex":
            # ask fails open on Codex: it marks the hook run failed and
            # continues the tool call, which is worse than no gate at all.
            return deny_decision(reason, runtime)
        return ask_decision(reason, runtime)
    # verdict is "Allow" or None (unaddressed by this principal's policy):
    # fall through silently to the existing tier-based default in
    # governed-repository-change.md.
    return None


def run_as_hook(stdin_payload: str, cwd: Path, runtime: str) -> int:
    """Read one PreToolUse event from stdin and print a decision, if any.

    Silent (prints nothing, exits 0) for malformed input, an unrelated tool
    call, a command outside a Git worktree, or any command this gate has no
    opinion on. The JSON on stdout decides the outcome for a matched, gated
    command or destination MCP mutation; exit code carries no meaning in this
    mode.
    """
    try:
        event = json.loads(stdin_payload)
    except json.JSONDecodeError:
        return 0

    # Claude Code and Codex both confirm "Bash" as the shell tool's name.
    # GitHub MCP mutation tools are admitted explicitly so they can share the
    # semantic GitHub permission namespace with the optional `gh` fallback.
    # Copilot's equivalent tool name is unverified as of AEPI-94, so its filter
    # remains permissive and command/tool presence below does the gating.
    tool_name = event.get("tool_name")
    if (
        runtime != "copilot"
        and tool_name is not None
        and tool_name != "Bash"
        and not is_governed_mcp_tool(tool_name)
    ):
        return 0

    root = repository_root(cwd)
    if root is None:
        return 0

    decision = hook_response(
        event.get("tool_input") or {}, event, root, runtime, tool_name
    )
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
