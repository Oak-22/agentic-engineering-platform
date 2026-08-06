# Agent Handoff Packet

Copy this structure and remove fields that do not apply. Keep the resulting
packet self-contained and concise.

```markdown
# Agent handoff: <outcome>

## Objective
<The user-visible result, not merely the next action.>

## Current state
- Work item: <key and direct link, if any>
- Workflow state: <verified status>
- Environment or repository: <stable identifier>

## Completed
- <Verified action and evidence>

## Capability boundary
- Current agent cannot: <specific blocked operation>
- Reason: <missing runtime, tool, permission, account, or specialization>
- Required target capability: <what the receiving agent must be able to do>

## Continue with
1. <First remaining action>
2. <Next action>

## Authority
- Authorized: <actions already within the user's request>
- Not authorized: <materially different, destructive, external, or expanded actions>
- Ask before: <conditions requiring renewed user approval>

## Canonical artifacts
- <path or URL — why it matters>

## Verification
- <observable success condition>

## Return
Return:
- <result or identifiers the originating agent needs>
- <verification evidence>
- <remaining blocker or follow-up, if any>
```

For a completion return, replace **Capability boundary** and **Continue with**
with:

```markdown
## Result
- <Completed action>

## Evidence
- <Verified state, output, identifier, or link>

## Resume
- <Any remaining work for the originating agent, or "None">
```
