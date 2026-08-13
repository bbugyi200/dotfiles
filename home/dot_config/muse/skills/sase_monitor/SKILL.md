---
name: sase_monitor
description:
  Run a long command without blocking your turn. Use this INSTEAD of any built-in
  monitor, background-task, or scheduled wake-up tool - those do not work in SASE, which
  runs agents for a single turn. Also use it to sleep/wait (for a CI job, a deploy, a
  rate limit) by monitoring a `sleep` command.
---

Use this skill when a command may take long enough that waiting inline would block the
agent turn, or when you need a timed sleep/wait before more work can happen.

## Core Rule

`sase monitor start` hands the command to a detached monitor supervisor and then kills
the current agent. The current provider turn will not return normally. Do not poll,
sleep, or wait for the monitored command yourself after starting it; put any
continuation work in `--next` so a follow-up agent can resume from the same workspace
and conversation.

Provider-native monitor, background-task, and scheduled wake-up tools do not work in
SASE's single-turn agent model. Use `sase monitor start` instead.

## Canonical Invocation

Run a long verification command and hand the result to a follow-up agent:

```bash
sase monitor start \
  --command 'just check-full' \
  --reason 'Verify the refactor before replying to the user' \
  --timeout 45m \
  --next 'Fix anything just check-full reported, then reply to the user.'
```

## Sleep Or Wait

Use `sleep` as the monitored command when you need to wait for CI, a deploy, a rate
limit, or a scheduled time. Custom statuses make the wait clear in agent lists:

```bash
sase monitor start \
  --command 'sleep 300' \
  --reason 'Wait for the CI run on PR #412 to finish' \
  --timeout 6m \
  --start-status 'SLEEPING FOR 300s' \
  --stop-status 'SLEPT FOR 300s' \
  --next 'Check the CI status for PR #412 with `gh pr checks 412`.'
```

## Fire And Forget

Omit `--next` when no follow-up agent should launch. The monitor still records the
command, reason, runtime, exit state, and retained output for later inspection:

```bash
sase monitor start \
  --command './collect-diagnostics.sh' \
  --reason 'Collect diagnostics for later inspection' \
  --timeout 20m
```

## Inspect Or Stop

- `sase monitor list` shows active monitors by default; add `--all` to include history.
- `sase monitor show <id>` shows details and the output tail; add `--follow` to stream
  until the monitor reaches a terminal state.
- `sase monitor stop <id>` stops a running monitor. Stopped monitors do not launch their
  recorded follow-up agent.

## Follow-Up Context

When `--next` is set, the follow-up agent receives the previous conversation through
`#fork`, the original reason, the requested next action, and a command-run breakdown:
outcome, exit code, elapsed time, output tail, and the path to the full captured log.

If the command times out, the follow-up still launches. Its breakdown says the command
did not finish and includes whatever output had been captured before the timeout.
