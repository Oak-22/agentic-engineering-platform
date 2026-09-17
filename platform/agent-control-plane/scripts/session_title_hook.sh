#!/bin/bash
# Claude Code session-title hook (user scope). Names the tab "<model> | <branch-or-folder>",
# or, when this session owns a governed delivery worktree,
# "<model> | <JIRA-KEY> | #<pr> <gate> | <branch>" where <gate> is ⏳ ✓ or ✗ from the PR's
# checks, and keeps it current unless the user renamed the tab themselves.
#
#   session_title_hook.sh start          SessionStart (startup|resume|fork)
#   session_title_hook.sh refresh        UserPromptSubmit
#   session_title_hook.sh model-switch   PostModelSwitch
#   session_title_hook.sh cleanup        SessionEnd
#
# State: ~/.claude/hooks/state/<session_id>.json = {model, title, userOwned, prBranch, pr,
#        gatePr, gate, gateAt}.
# That folder is runtime output, not source. Registered in ~/.claude/settings.json; inventoried in
# agent-assets/hooks/hooks_registry.json; documented in agent-assets/hooks/session-title.md.

STATE_DIR=~/.claude/hooks/state
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
STATE="$STATE_DIR/$SESSION_ID.json"

emit_none() { echo '{}'; exit 0; }

# Branch when there is one; otherwise the folder name stands in for it, so a directory that
# is not a git repo (or a detached HEAD) still gets a title instead of leaving the tab to
# the auto-titler.
where() {
  local cwd="$1" w
  w=$(git -C "$cwd" branch --show-current 2>/dev/null)
  [ -z "$w" ] && w=$(basename "$cwd")
  echo "$w"
}

# The primary checkout stays pinned to the workbench during governed delivery, so its branch
# says nothing about what this session is delivering. The worktree claim registry does: it
# records the delivery branch per owning agent, and the owner id is this session's id. Prints
# the claimed branch, or nothing when this session owns no active claim or the repository
# has no registry (the hook is user-scope and fires in every repository).
claimed_branch() {
  local cwd="$1" top script
  top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || return 0
  script="$top/platform/agent-control-plane/scripts/delivery_worktrees.py"
  [ -f "$script" ] || return 0
  (cd "$top" && python3 "$script" list --format json 2>/dev/null) \
    | jq -r --arg a "claude:${SESSION_ID:0:8}" \
        '[.[] | select(.status == "active" and .agent == $a)][0].branch // empty'
}

# The pull request number costs a network round-trip, so it is resolved once per claimed
# branch and cached in the state file; a later refresh re-resolves only when the branch
# changes or no PR was found yet. Prints "#N" or nothing.
pr_for() {
  local branch="$1" cached_branch cached_pr n
  cached_branch=$(jq -r '.prBranch // ""' "$STATE")
  cached_pr=$(jq -r '.pr // ""' "$STATE")
  if [ "$cached_branch" = "$branch" ] && [ -n "$cached_pr" ]; then
    echo "#$cached_pr"; return 0
  fi
  n=$(gh pr list --head "$branch" --state open --json number --jq '.[0].number // empty' 2>/dev/null)
  jq --arg b "$branch" --arg n "$n" '.prBranch = $b | .pr = $n' "$STATE" > "$STATE.tmp" \
    && mv "$STATE.tmp" "$STATE"
  [ -n "$n" ] && echo "#$n"
}

# The PR's check state is the thing a delivery session is usually waiting on, and it lives
# in GitHub rather than in the session, so it can be shown even while the main thread is
# idle behind a monitor. One `gh pr checks` call costs about a second, so it is cached in
# the state file as {gate, gateAt} and re-queried only when there is no cached state, when
# the cached state is pending and older than 60 s, or when it is settled and older than
# 10 min (a new push reopens the gate). Prints one glyph, or nothing when unknown.
gate_for() {
  local pr="$1" cached gate at now age ttl state
  cached=$(jq -r '.gatePr // ""' "$STATE")
  gate=$(jq -r '.gate // ""' "$STATE")
  at=$(jq -r '.gateAt // 0' "$STATE")
  now=$(date +%s); age=$((now - at))
  ttl=600; [ "$gate" = "pending" ] && ttl=60
  if [ "$cached" = "$pr" ] && [ -n "$gate" ] && [ "$age" -lt "$ttl" ]; then
    state="$gate"
  else
    state=$(gh pr checks "${pr#\#}" --json name,bucket --jq \
      'if length==0 then "" elif any(.[]; .bucket=="fail") then "fail"
       elif any(.[]; .bucket=="pending") then "pending"
       elif all(.[]; .bucket=="pass" or .bucket=="skipping") then "pass" else "" end' 2>/dev/null)
    jq --arg p "$pr" --arg g "$state" --argjson t "$now" '.gatePr = $p | .gate = $g | .gateAt = $t' \
      "$STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
  fi
  case "$state" in
    pending) echo "⏳" ;;
    pass)    echo "✓" ;;
    fail)    echo "✗" ;;
  esac
}

# "<model> | <branch-or-folder>" outside delivery; with a claim, the Jira key (the branch's
# second segment), the PR and its gate state when known, then the branch.
title_for_session() {
  local model="$1" cwd="$2" branch key pr gate
  branch=$(claimed_branch "$cwd")
  if [ -z "$branch" ]; then
    title_for "$model" "$(where "$cwd")"; return 0
  fi
  key=$(echo "$branch" | cut -d/ -f2 | grep -oE '^[A-Z][A-Z0-9]+-[0-9]+')
  pr=$(pr_for "$branch")
  [ -n "$pr" ] && gate=$(gate_for "$pr")
  echo "${model#claude-} | ${key:-?}${pr:+ | $pr${gate:+ $gate}} | $branch"
}

# The vendor prefix in the model ID ("claude-opus-5") is redundant in a tab.
title_for() { echo "${1#claude-} | $2"; }

case "$1" in

start)
  MODEL=$(echo "$INPUT" | jq -r '.model // empty')
  CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
  SESSION_TITLE=$(echo "$INPUT" | jq -r '.session_title // empty')
  mkdir -p "$STATE_DIR"
  [ -z "$SESSION_ID" ] || [ -z "$MODEL" ] && emit_none

  # `session_title` reports whatever title is already set, which on a resume or fork is the
  # title THIS hook set before the session was suspended. It is therefore not evidence of a
  # /rename on its own, and treating it as such makes the hook disown a title it owns —
  # permanently, since the disowning write also destroys the record that proved ownership.
  # Ownership is tracked explicitly instead: a returning title that matches what we last set
  # is still ours.
  PRIOR_TITLE=""; PRIOR_USER_OWNED=false
  if [ -f "$STATE" ]; then
    PRIOR_TITLE=$(jq -r '.title // ""' "$STATE")
    PRIOR_USER_OWNED=$(jq -r '.userOwned // false' "$STATE")
  fi
  USER_OWNED=false
  if [ "$PRIOR_USER_OWNED" = "true" ]; then
    USER_OWNED=true
  elif [ -n "$SESSION_TITLE" ] && [ "$SESSION_TITLE" != "$PRIOR_TITLE" ]; then
    USER_OWNED=true
  fi
  if [ "$USER_OWNED" = "true" ]; then
    jq -n --arg m "$MODEL" '{model: $m, title: "", userOwned: true}' > "$STATE"
    emit_none
  fi

  # Seed the state before deriving the title, since pr_for caches into it.
  jq -n --arg m "$MODEL" '{model: $m, title: "", userOwned: false}' > "$STATE"
  TITLE=$(title_for_session "$MODEL" "$CWD")
  jq --arg t "$TITLE" '.title = $t' "$STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
  jq -n --arg t "$TITLE" '{hookSpecificOutput: {hookEventName: "SessionStart", sessionTitle: $t}}'
  ;;

refresh)
  CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
  SESSION_TITLE=$(echo "$INPUT" | jq -r '.session_title // empty')
  [ -z "$SESSION_ID" ] || [ ! -f "$STATE" ] && emit_none
  [ "$(jq -r '.userOwned // false' "$STATE")" = "true" ] && emit_none

  OWNED=$(jq -r '.title // ""' "$STATE")
  # A title we did not set has appeared mid-session, so the user renamed it. Record that once
  # and leave the title alone from here on.
  if [ -n "$OWNED" ] && [ -n "$SESSION_TITLE" ] && [ "$SESSION_TITLE" != "$OWNED" ]; then
    jq '.userOwned = true | .title = ""' "$STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
    emit_none
  fi

  MODEL=$(jq -r '.model // empty' "$STATE")
  [ -z "$MODEL" ] && emit_none
  TITLE=$(title_for_session "$MODEL" "$CWD")
  [ "$TITLE" = "$OWNED" ] && emit_none
  jq --arg t "$TITLE" '.title = $t' "$STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
  jq -n --arg t "$TITLE" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", sessionTitle: $t}}'
  ;;

model-switch)
  TO_MODEL=$(echo "$INPUT" | jq -r '.to_model // empty')
  [ -z "$SESSION_ID" ] || [ -z "$TO_MODEL" ] && emit_none
  mkdir -p "$STATE_DIR"
  # PostModelSwitch cannot set sessionTitle; only record the new model and let the next
  # refresh notice the change.
  if [ -f "$STATE" ]; then
    jq --arg m "$TO_MODEL" '.model = $m' "$STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
  else
    jq -n --arg m "$TO_MODEL" '{model: $m, title: "", userOwned: false}' > "$STATE"
  fi
  emit_none
  ;;

cleanup)
  [ -n "$SESSION_ID" ] && rm -f "$STATE"
  emit_none
  ;;

*)
  echo "usage: $0 start|refresh|model-switch|cleanup  (reads hook JSON on stdin)" >&2
  exit 2
  ;;
esac
