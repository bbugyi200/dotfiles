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

## Compose The Requested Prompt

The requested prompt is a full sase prompt: `%` directives and `#` xprompt references all work. Before submitting, think
hard about the workspace and wait choices below; they determine where the agent runs and which changes it sees.

### VCS Workspace xprompt

Standalone (non-family) prompts should normally start with a VCS workspace reference:

- `#gh:<ref>` (GitHub), `#git:<ref>` (bare git), `#hg:<ref>` (Mercurial), or `#cd:<path>` (plain directory, no VCS
  workspace management).
- `<ref>` is usually a project name (`#gh:sase`). Use a ChangeSpec name (`#gh:my_change`) only when the agent must
  continue that existing CL/PR branch, or `#gh:@agent` to target the ChangeSpec created by the named agent.
- A prompt with no workspace reference defaults to `#git:home`, which is usually wrong for repo work.
- Family-attach launches (`%n(parent, suffix)`) inherit the parent's workspace and ChangeSpec; do not add a workspace
  reference to them.

### Wait Directive

`%w(<agent>)` parks the launch until the named agent completes successfully. The workspace is checked out only after the
wait resolves, so the new agent sees the awaited agent's landed changes. Think hard about whether you need it:

- Wait on your own agent name (from `$SASE_AGENT_NAME`) when the new agent must build on changes this run has not landed
  yet; wait on another agent's name when it depends on that agent instead.
- Omit `%w` when the work is independent, so the agent starts immediately.
- Failed or killed runs never satisfy `%w`; the launch stays parked until a successful run of that name exists.
- `%w(time=10m)` defers by time instead; arguments compose: `%w(planner, time=5m)`.

### Other xprompts

`#name` / `#name(args)` references expand reusable templates and multi-step workflows: they can inject prompt text, run
python/bash steps, set environment variables, and split work across multiple agents. Rollover workflows `#commit`,
`#propose`, and `#pr(<name>)` control how the launched agent's changes land. Discover what is available with
`sase xprompt list`; preview a prompt's expansion with `sase xprompt expand '<prompt>'`.

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
