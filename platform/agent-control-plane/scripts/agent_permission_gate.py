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
separate, later change.

Destination MCP tool names are classified by consequence rather than by
membership in a name allowlist (AEPI-132). Three outcomes are possible:

- an explicitly mapped operation resolves to a semantic action the policy
  decides on;
- a verb-prefixed read resolves to `<destination>:tool:read`, which the
  policy allows affirmatively so the call does not prompt;
- anything else returns no opinion, and the runtime's own permission flow
  decides.

The earlier arrangement was the inverse: an unmapped destination tool became
`<destination>:tool:unclassified` and was denied. That inverted the gate
relative to consequence — it denied reads such as `getTransitionsForJiraIssue`
while leaving Confluence writes entirely unclassified — and it required a gate
change every time a connected MCP server added or renamed a tool. The set of
genuinely irreversible actions does not grow at that rate, so those are
enumerated instead.
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

# AEPI-132 collapsed the six specialist principals into this one. Role
# separation never produced a separation of duties — a specialist subagent is
# the same model, in the same session, adopting a role it chose for itself —
# so the boundary that matters is enforced here and by the independent
# Copilot review on the pull request, not by which name the runtime used to
# spawn a subagent. `resolve_agent_type` therefore maps every runtime
# identity, built-in or custom, onto the single generalist policy unless a
# policy document with that exact name exists; it never default-permits.

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
GH_PR_EDIT_PATTERN = re.compile(r"\bgh\s+pr\s+edit\b")
GH_PR_READY_PATTERN = re.compile(r"\bgh\s+pr\s+ready\b")
GH_PR_CLOSE_PATTERN = re.compile(r"\bgh\s+pr\s+close\b")
GH_PR_UPDATE_BRANCH_PATTERN = re.compile(r"\bgh\s+pr\s+update-branch\b")
GH_PR_REVIEW_PATTERN = re.compile(r"\bgh\s+pr\s+review\b")
DELIVERY_PUBLISH_PATTERN = re.compile(
    r"^\s*(?:(?:\S*/)?python3\s+)?(?:\./)?"
    r"platform/agent-control-plane/scripts/publish_delivery_branch\.py\b"
    r"(?=[^|;&\n]*--execute\b)[^|;&\n]*$"
)
DELIVERY_CLEANUP_PATTERN = re.compile(
    r"^\s*(?:(?:\S*/)?python3\s+)?(?:\./)?(?:"
    r"platform/agent-control-plane/agent-assets/skills/manage-git-workflow/scripts/"
    r"|\.agents/skills/manage-git-workflow/scripts/)delivery_cleanup\.py\s+pr\b"
    r"(?=[^|;&\n]*--execute\b)[^|;&\n]*$"
)

GITHUB_MCP_ACTIONS = {
    "create_pull_request": "github:pull_request:create",
    "update_pull_request": "github:pull_request:update",
    "update_pull_request_branch": "github:pull_request:sync",
    "request_copilot_review": "github:pull_request:copilot-review:request",
    "add_reply_to_pull_request_comment": "github:pull_request:review-thread:reply",
    "pull_request_review_write": "github:pull_request:review:comment",
    "merge_pull_request": "github:pull_request:merge",
    # Remote-content writes bypass the local governed publication path
    # entirely, so they carry the same consequence as a push and are named
    # rather than left to the read/no-opinion split below.
    "create_or_update_file": "github:repository:content:write",
    "push_files": "github:repository:content:write",
    "delete_file": "github:repository:content:delete",
    "create_branch": "github:branch:create",
    "delete_repository": "github:repository:delete",
}
JIRA_MCP_ACTIONS = {
    "createjiraissue": "jira:issue:create",
    "editjiraissue": "jira:issue:update",
    "transitionjiraissue": "jira:issue:transition",
    "createissuelink": "jira:issue:link",
    "addcommenttojiraissue": "jira:issue:comment",
    "addworklogtojiraissue": "jira:issue:worklog",
}
CONFLUENCE_MCP_ACTIONS = {
    "createconfluencepage": "confluence:page:create",
    "updateconfluencepage": "confluence:page:update",
    "createconfluencefootercomment": "confluence:comment:create",
    "createconfluenceinlinecomment": "confluence:comment:create",
}

#: A destination tool whose operation opens with one of these verbs reads
#: rather than writes. Recognizing reads by shape rather than by name is what
#: lets a connected server add or rename a read tool without a gate change.
#: No word boundary is required after the verb: the Codex Rovo connector
#: lowercases and flattens its operations (`atlassian_rovo_getjiraissue`), so
#: requiring one would classify half the Jira read surface as unrecognized.
#: The cost is that a mutation named like a read would read as one — which is
#: why every named mutation is matched first, before this test runs.
MCP_READ_VERB_PATTERN = re.compile(
    r"^(?:get|list|search|fetch|read|lookup|find|view)"
)

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
    if DELIVERY_PUBLISH_PATTERN.search(command):
        branch = current_branch(root) or "*"
        return ActionMatch(
            "git:delivery:publish", f"git:{REPO_NAME}:branch/{branch}"
        )
    if DELIVERY_CLEANUP_PATTERN.search(command):
        return ActionMatch(
            "git:delivery:cleanup", f"git:{REPO_NAME}:delivery/merged-pr"
        )
    if GIT_PUSH_DELETE_PATTERN.search(command):
        return ActionMatch("git:branch:delete", f"git:{REPO_NAME}:branch/*")
    if GIT_PUSH_PATTERN.search(command):
        branch = pushed_branch(command, root)
        return ActionMatch("git:push", f"git:{REPO_NAME}:branch/{branch}")
    if GIT_BRANCH_DELETE_PATTERN.search(command):
        return ActionMatch("git:branch:delete", f"git:{REPO_NAME}:branch/*")
    if GH_PR_MERGE_PATTERN.search(command):
        return ActionMatch("github:pull_request:merge", f"github:{REPO_NAME}:*")
    if GH_PR_CLOSE_PATTERN.search(command):
        return ActionMatch("github:pull_request:close", f"github:{REPO_NAME}:*")
    if GH_PR_READY_PATTERN.search(command):
        return ActionMatch("github:pull_request:ready", f"github:{REPO_NAME}:*")
    if GH_PR_UPDATE_BRANCH_PATTERN.search(command):
        return ActionMatch("github:pull_request:sync", f"github:{REPO_NAME}:*")
    if GH_PR_EDIT_PATTERN.search(command):
        action = (
            "github:pull_request:retarget"
            if re.search(r"(?:^|\s)--base(?:\s|=)", command)
            else "github:pull_request:update"
        )
        return ActionMatch(action, f"github:{REPO_NAME}:*")
    if GH_PR_REVIEW_PATTERN.search(command):
        if re.search(r"(?:^|\s)--approve(?:\s|$)", command):
            action = "github:pull_request:approve"
        elif re.search(r"(?:^|\s)--request-changes(?:\s|$)", command):
            action = "github:pull_request:request-changes"
        else:
            action = "github:pull_request:review:comment"
        return ActionMatch(action, f"github:{REPO_NAME}:*")
    if GH_PR_CREATE_PATTERN.search(command):
        action = (
            "github:pull_request:create"
            if re.search(r"(?:^|\s)--draft(?:\s|$)", command)
            else "github:pull_request:create-ready"
        )
        return ActionMatch(action, f"github:{REPO_NAME}:*")
    return None


def mcp_destination(tool_name: object) -> str | None:
    """Which governed destination a runtime tool name addresses, if any.

    Confluence is checked before the generic Atlassian match so that an
    `mcp__atlassian__updateConfluencePage` call — which the earlier
    Jira-only test never saw at all — lands on the Confluence namespace
    rather than falling through unclassified.
    """
    if not isinstance(tool_name, str):
        return None
    lowered = tool_name.lower()
    for token in ("github", "confluence", "jira", "atlassian"):
        if token in lowered:
            return token
    normalized = re.sub(r"[^a-z0-9]", "", lowered)
    known = (*JIRA_MCP_ACTIONS, *CONFLUENCE_MCP_ACTIONS)
    if any(normalized.endswith(operation) for operation in known):
        return "jira" if normalized.endswith(tuple(JIRA_MCP_ACTIONS)) else "confluence"
    return None


def is_governed_mcp_tool(tool_name: object) -> bool:
    return mcp_destination(tool_name) is not None


def mcp_operation(tool_name: str) -> str:
    """The bare operation segment of an `mcp__<server>__<tool>` name."""
    return tool_name.rsplit("__", 1)[-1]


def is_mcp_read_operation(operation: str) -> bool:
    """Whether an operation name reads rather than writes.

    Tested at every `_` boundary, not only at the start, because a server may
    flatten its namespace into the tool name: the Codex Rovo connector exposes
    `getJiraIssue` as `atlassian_rovo_getjiraissue`. Only a leading read verb
    counts at each boundary, so a mutation that merely contains a read word
    (`add_reply_to_pull_request_comment`, `create_or_update_file`) is not
    mistaken for one — and for every destination the named-mutation map is
    consulted before this test runs.
    """
    if operation.endswith("_read"):
        return True
    candidate = operation
    while candidate:
        if MCP_READ_VERB_PATTERN.match(candidate):
            return True
        _, separator, candidate = candidate.partition("_")
        if not separator:
            return False
    return False


def _github_resource(tool_input: dict) -> str:
    repository = tool_input.get("repository")
    if isinstance(repository, dict):
        owner = repository.get("owner")
        name = repository.get("name") or repository.get("repo")
        repository = f"{owner}/{name}" if owner and name else None
    elif not isinstance(repository, str):
        owner = tool_input.get("owner")
        name = tool_input.get("repo") or tool_input.get("name")
        repository = f"{owner}/{name}" if owner and name else None
    return f"github:{repository}:*" if repository else f"github:{REPO_NAME}:*"


def _refine_github_action(action: str, operation: str, tool_input: dict) -> str:
    if operation == "create_pull_request" and tool_input.get("draft") is not True:
        return "github:pull_request:create-ready"
    if operation == "update_pull_request":
        if tool_input.get("base") is not None:
            return "github:pull_request:retarget"
        state = str(tool_input.get("state", "")).lower()
        if state == "closed":
            return "github:pull_request:close"
        if state == "open":
            return "github:pull_request:reopen"
        if tool_input.get("reviewers") is not None:
            return "github:pull_request:reviewer:update"
        if tool_input.get("draft") is False:
            return "github:pull_request:ready"
    if operation == "pull_request_review_write":
        method = str(tool_input.get("method", "")).lower()
        event = str(tool_input.get("event", "")).upper()
        if method == "resolve_thread":
            return "github:pull_request:review-thread:resolve"
        if method == "unresolve_thread":
            return "github:pull_request:review-thread:unresolve"
        if event == "APPROVE":
            return "github:pull_request:approve"
        if event == "REQUEST_CHANGES":
            return "github:pull_request:request-changes"
    return action


def recognize_mcp_action(tool_name: object, tool_input: dict) -> ActionMatch | None:
    """Classify a destination MCP call by consequence.

    Returns a named mutation action, a `<destination>:tool:read` action, or
    None. None means this gate has no opinion and the runtime's own
    permission flow decides — the deliberate inversion of the earlier
    `<destination>:tool:unclassified` deny (AEPI-132).
    """
    destination = mcp_destination(tool_name)
    if destination is None:
        return None
    operation = mcp_operation(str(tool_name))

    if destination == "github":
        action = GITHUB_MCP_ACTIONS.get(operation)
        if action is not None:
            return ActionMatch(
                _refine_github_action(action, operation, tool_input),
                _github_resource(tool_input),
            )
        if is_mcp_read_operation(operation):
            return ActionMatch("github:tool:read", "github:*")
        return None

    normalized = re.sub(r"[^a-z0-9]", "", operation.lower())

    for actions, namespace in ((CONFLUENCE_MCP_ACTIONS, "confluence"), (JIRA_MCP_ACTIONS, "jira")):
        matched = next(
            (item for item in actions if normalized.endswith(item)), None
        )
        if matched is None:
            continue
        action = actions[matched]
        if namespace == "confluence":
            space = tool_input.get("spaceKey") or tool_input.get("spaceId") or "*"
            page = tool_input.get("pageId") or tool_input.get("id") or "*"
            return ActionMatch(action, f"confluence:{space}:page/{page}")
        issue = (
            tool_input.get("issueIdOrKey")
            or tool_input.get("issueKey")
            or tool_input.get("issue_key")
            or "*"
        )
        project = tool_input.get("projectKey") or tool_input.get("project_key") or "*"
        return ActionMatch(action, f"jira:{project}:issue/{issue}")

    if is_mcp_read_operation(operation):
        return ActionMatch(f"{destination}:tool:read", f"{destination}:*")
    return None


def resolve_agent_type(event: dict) -> str:
    """Resolve the principal for one event, never default-permitting.

    Exactly one policy document ships today, so every runtime identity —
    built-in fallback, custom subagent, or an unrecognized string — resolves
    to it. The `load_policy` probe is kept so that adding a policy document
    remains sufficient to introduce a principal, rather than also requiring
    an alias-table edit.
    """
    raw = event.get("agent_type")
    if not raw:
        return DEFAULT_AGENT_TYPE
    raw = str(raw)
    if load_policy(raw) is not None:
        return raw
    return DEFAULT_AGENT_TYPE


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


def allow_decision(reason: str, runtime: str = "claude") -> dict:
    """Affirmatively authorize a call the policy already allows outright.

    Claude Code treats `allow` as "skip the interactive permission prompt"
    while still applying deny and ask rules on top, so this cannot be used to
    escape a deny. Emitting it is a governance decision, not a cosmetic one:
    the earlier silent fall-through kept the operator as a backstop, and an
    affirmative allow removes that backstop for exactly the actions a policy
    statement names. Only an `Allow` verdict — a statement that matched with
    no `requiresHumanApproval` condition — reaches here; an action no
    statement addresses still falls through silently.

    Safe to emit on Codex: an unrecognized decision there fails open, which
    is the same outcome the allow expresses.
    """
    return _decision(runtime, "allow", reason)


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
    if verdict == "Allow":
        return allow_decision(
            f"{match.action} on {match.resource} is allowed without approval "
            f"under policy {policy.get('policyId', agent_type)}.",
            runtime,
        )
    # verdict is None: no statement addressed this action, so fall through
    # silently to the existing tier-based default in
    # governed-repository-change.md and the runtime's own permission flow.
    return None


def run_as_hook(stdin_payload: str, cwd: Path, runtime: str) -> int:
    """Read one PreToolUse event from stdin and print a decision, if any.

    Silent (prints nothing, exits 0) for malformed input, an unrelated tool
    call, a command outside a Git worktree, or any command this gate has no
    opinion on. The JSON on stdout decides the outcome for a matched command
    or destination MCP call — allow, ask, or deny; exit code carries no
    meaning in this mode.
    """
    try:
        event = json.loads(stdin_payload)
    except json.JSONDecodeError:
        return 0

    # Claude Code and Codex both confirm "Bash" as the shell tool's name.
    # Destination MCP tools are admitted explicitly so they can share the
    # semantic permission namespace with the optional `gh` fallback.
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
