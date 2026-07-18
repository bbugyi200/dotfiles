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

The command creates a durable pending `LaunchApproval` and waits mechanically for its terminal response. It does not
spawn an agent unless the approver accepts the request and host dispatch succeeds.

The pending request lives in SASE's neutral `interaction_requests/launch/<request-id>/` layout. Every terminal option
uses the bundle's hash-verified command; do not write the legacy launch-request tree or execute a command from the
request bundle yourself.

A prompt containing `---` separator lines outside fenced code blocks plans one slot per segment. Set `max_slots` at
least to the segment count; otherwise the request fails with `max_slots_exceeded`.

## Compose The Requested Prompt

The requested prompt is a full sase prompt: `%` directives and `#` xprompt references all work. Before submitting, think
hard about the workspace and wait choices below; they determine where the agent runs and which changes it sees.

### VCS Workspace xprompt

Prompts that are not family attachments should normally start with a VCS workspace reference:

- `#gh:<ref>` (GitHub), `#git:<ref>` (bare git), or another ref registered by an installed workspace plugin.
- `<ref>` is usually a project name (`#gh:sase`). Use a ChangeSpec name (`#gh:my_change`) only when the agent must
  continue that existing PR branch, or `#gh:@agent` to target the ChangeSpec created by the named agent.
- A prompt with no workspace reference defaults to `#git:home`, which is usually wrong for repo work.
- Family-attach launches (`%n(parent, suffix)`) inherit the parent's workspace and ChangeSpec; do not add a workspace
  reference to them.

### Wait Directive

`%w(<agent>)` parks the launch until the named agent completes successfully. The workspace is checked out only after the
wait resolves, so the new agent sees the awaited agent's landed changes. `%w(@<tribe>)` instead binds to the next agent
or clan launched into that tribe after the waiting launch. Think hard about whether you need it:

- Wait on your own agent name (from `$SASE_AGENT_NAME`) when the new agent must build on changes this run has not landed
  yet; wait on another agent's name when it depends on that agent instead.
- Omit `%w` when the work is independent, so the agent starts immediately.
- Failed or killed runs never satisfy `%w`; the launch stays parked until a successful run of that name exists.
- `%w(time=10m)` defers by time instead; arguments compose: `%w(planner, time=5m)`.
- A tribe wait binds to the earliest qualifying successful entity launched after the waiter. For a clan, every member
  must complete successfully.

### Other xprompts

`#name` / `#name(args)` references expand reusable templates and multi-step workflows: they can inject prompt text, run
python/bash steps, set environment variables, and split work across multiple agents. Rollover workflows `#commit`,
`#propose`, and `#pr(<name>)` control how the launched agent's changes land. Discover what is available with
`sase xprompt list`; preview a prompt's expansion with `sase xprompt expand '<prompt>'`.

`#fork:<agent>` continues from one agent's chat. `#fork:<clan>` injects every clan member's sanitized prompts plus reply
outcome, model, launch time, size statistics, and transcript path; full member replies are intentionally omitted so the
child can open only the transcripts it needs. `#fork:@<tribe>` implies the matching tribe wait and then forks the same
next entity, using the lean clan block when that entity is a clan.

### Literal Directive Text

The requested prompt is re-parsed at dispatch: every `%` directive and `#` reference anywhere in it is live, even
mid-sentence. A stray `#git:<ref>` in prose silently re-targets the workspace; a stray `%m` mention fails the launch
after approval. When the prompt must show prompt syntax literally (docs, demos, tests):

- Put the literal syntax in a fenced code block; fenced content is never parsed.
- Or enclose a prose region between `%xprompts_enabled:false` and `%xprompts_enabled:true` marker lines; the markers are
  stripped before the launched agent sees the prompt.
- Otherwise name the syntax in words ("the model directive") instead of writing the token.

Always preflight with `sase xprompt expand '<prompt>'`: it must succeed and report only the directives and references
you intended.

## Sequential Family Members

To attach the approved launch to an existing family, put the family directive in the requested prompt:

```text
%n(parent, reviewer)
Review the current result and report whether it is ready.
```

Use `%n(parent, @)` only when the next free feedback suffix is acceptable. Use a concrete suffix such as
`%n(parent, tester)` when the role matters.

## Parallel Clan Members

To launch parallel agents as one rootless clan, give every segment the same clan directive and name every member inside
that clan's hood:

```text
%n:review.security %clan:review
Audit the security boundary.
---
%n:review.performance %clan:review
Audit the performance boundary.
```

The clan name is reserved and is never an agent. `%clan` does not add ordering; use `%wait` explicitly. Set `max_slots`
to at least the number of segments in the request.

Use `%clan(review, tribe=quality)` (or `%c(review, tribe=quality)`) when the clan should appear in a tribe. Keep
`%tribe:quality` / `%t:quality` for standalone agents and sequential families that are not clan members. Never combine
`%tribe` with `%clan`; move the tribe into the clan declaration instead.

## Handle The Outcome

The command returns only after approval, rejection, feedback, dispatch failure, cancellation, or timeout. Read its
single JSON result; do not poll request files yourself.

Approved responses look like:

```json
{
  "status": "approved",
  "selected_option_ids": ["approve"],
  "message": "Launch approved and dispatched 1 agent"
}
```

Rejected or feedback responses use `status` values `rejected` and `feedback`. A host dispatch failure uses
`dispatch_failed` and includes the failure detail in `message`.

```json
{
  "status": "feedback",
  "selected_option_ids": ["feedback"],
  "message": "Launch rejected with feedback"
}
```

If rejected, do not spawn anyway. Use the feedback to revise the request or continue without launching.
