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

## Hazards

- The command runs under the shell (`sh -c` on Unix). Quote paths, variables, and nested
  commands exactly as you would in a shell script.
- Only one monitor can be active in a lane. An identical replay returns the existing
  monitor; a different request errors until the active monitor settles.
- Do not monitor interactive or TTY-requiring commands. Use monitors for batch commands,
  sleeps, deploy checks, and other noninteractive waits.
- Output is bounded and can rotate. Use `sase monitor show <id> --all-lines` or the log
  path from the follow-up prompt for retained output, not an assumption that every byte
  is preserved forever.
- Do not poll, sleep, or wait after `sase monitor start`; the starting agent is handed
  off and killed when running inside an agent.

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

Do not add `--idle-timeout` to an intentional quiet wait unless the sleep itself should
be treated as stalled.

## Fire And Forget

Omit `--next` when no follow-up agent should launch. The monitor still records the
command, reason, runtime, exit state, and retained output for later inspection:

```bash
sase monitor start \
  --command './collect-diagnostics.sh' \
  --reason 'Collect diagnostics for later inspection' \
  --timeout 20m
```

## Useful Flags

- `--cwd DIR` runs the command from a specific directory. The default is the lane's
  workspace when SASE can resolve it, otherwise the current directory.
- `--lane NAME` targets a specific agent lane. Inside an agent, the current lane is the
  default; outside an agent, pass it explicitly.
- `--label TEXT` controls the short row label shown in monitor lists.
- `--tail-lines N` controls how many output lines are included when `--next-output tail`
  is used for the follow-up prompt.
- `--idle-timeout DURATION` kills a command that produces no bytes for that duration.
  Omit it for valid quiet commands such as `sleep`.
- `--next-output none|tail|file` controls output handed to the follow-up. `tail` embeds
  the retained tail as fenced untrusted output, `file` names the log file, and `none`
  includes only the outcome summary plus a `sase monitor show --all-lines` pointer.

## Inspect Or Stop

- `sase monitor list` shows active monitors by default; add `--all` to include history.
- `sase monitor show <id>` shows details and the output tail; add `--follow` to stream
  until the monitor reaches a terminal state.
- `sase monitor stop <id>` stops a running monitor. Stopped monitors do not launch their
  recorded follow-up agent.

## Follow-Up Context

When `--next` is set, the follow-up agent receives the previous conversation through
`#fork`, the original reason, the requested next action, and a command-run breakdown:
outcome, exit code, elapsed time, selected output policy, and the path to the retained
captured log.

With `--next-output tail`, the retained tail is fenced and labeled as untrusted command
output. With `--next-output file`, the follow-up gets the log path instead of embedded
output. With `--next-output none`, it gets only the outcome summary and a
`sase monitor show --all-lines` pointer.

If the command fails or times out, the follow-up still launches. Its breakdown says
whether the total timeout or idle timeout fired. If the monitor is stopped manually or
marked `lost` after a reboot, the recorded follow-up does not launch.
