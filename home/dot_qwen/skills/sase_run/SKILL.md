---
name: sase_run
description: Request a SASE agent launch through LaunchApproval instead of spawning directly.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_run --reason "<one-line reason for using this skill>"
```

Use this skill when you need to start another SASE agent from inside a running agent. Agent-initiated launches must be
requested through `LaunchApproval`.

Do not run `sase run` or `sase run -d` directly from an agent. Those paths are for user-initiated launches.

## Request A Launch

Write a JSON request file:

```json
{
  "schema_version": 1,
  "prompt": "%n(parent, reviewer)\nReview the proposed implementation and report issues.",
  "reason": "Need a reviewer family member before continuing.",
  "approval": "required",
  "max_slots": 1
}
```

Then submit it:

```bash
sase launch request -f launch_request.json -o json
```

The command creates `launch_request.json`, `launch_preview.md`, and a pending `LaunchApproval`; it does not spawn the
agent.

## Family Members

To attach the approved launch to an existing family, put the family directive in the requested prompt:

```text
%n(parent, reviewer)
Review the current result and report whether it is ready.
```

Use `%n(parent, @)` only when the next free feedback suffix is acceptable. Use a concrete suffix such as
`%n(parent, tester)` when the role matters.

## Handle The Outcome

The JSON output includes `response_file`. Poll that path until `launch_response.json` appears.

Approved responses look like:

```json
{ "action": "approve", "dispatch_status": "launched", "launched_count": 1 }
```

Rejected responses look like:

```json
{ "action": "reject", "feedback": "Narrow the requested launch." }
```

If rejected, do not spawn anyway. Use the feedback to revise the request or continue without launching.
