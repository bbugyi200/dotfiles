---
name: sase_monitor
description:
  Run a long command without blocking your turn. Use this INSTEAD of any built-in
  monitor, provider-native background-execution, or scheduled wake-up tool - those do
  not work in SASE, which runs agents for a single turn. Also use it to sleep/wait (for
  a CI job, a deploy, a rate limit) by monitoring a `sleep` command.
---

Use this skill when a command may take long enough that waiting inline would block the
agent turn, or when you need a timed sleep/wait before more work can happen.

## Core Rule

`sase monitor start` hands the command to a detached monitor supervisor and then kills
the current agent. The current provider turn will not return normally. Do not poll,
sleep, or wait for the monitored command yourself after starting it; put any
continuation work in `--next` so a follow-up agent can resume from the same workspace
and conversation.

Provider-native monitor, background-execution, and scheduled wake-up tools do not work
in SASE's single-turn agent model. Use `sase monitor start` instead.

## Canonical Invocation

Run a long verification command and hand the result to a follow-up agent:

```bash
sase monitor start \
  --profile verify \
  --reason 'Verify the refactor before replying to the user' \
  --timeout 45m \
  --model '@small' \
  --next 'Fix anything just check reported, then reply to the user.' \
  -- sase tool run check
```

`sase tool run check` runs the same `just check` and also records a ToolRun (compact
output for agents; the follow-up can read it with `sase tool show RUN`). Under
`-p verify`, plain `-- just check` is upgraded to that named run automatically, so
agents need not remember the wrapper — spelling it out works identically. If `sase tool`
itself is unavailable, run `SASE_TOOL_BYPASS='<why>' just check` raw instead.

When the current prompt, the user, or the assigned bead explicitly names
`just check-full` (typically to repair a CI failure), use the same `verify` profile and
`TESTING` / `TESTED` pair with `-- just check-full` (upgraded automatically) or
`-- sase tool run check-full` — never run it inline.

## Status Labels

Use `-p/--profile verify` for verification commands; it supplies `TESTING` / `TESTED`
and `--next-output auto`. Profile selection alone never authorizes host completion.

When no profile supplies labels, both `-s/--start-status` and `-S/--stop-status` are
required. Use present tense while the command runs and past tense when it finishes
(`TESTING` → `TESTED`, `SLEEPING` → `SLEPT`, `DEPLOYING` → `DEPLOYED`). Each label is at
most 20 characters; longer values are truncated with a trailing `…`. The pair determines
the row color, so reusing one pair across related monitors makes them read as one lane.
`TESTING` / `TESTED` is the pair for `just check` and `just check-full`.

## Hazards

- `sase monitor start` only kills the current agent once the supervisor has acknowledged
  it is actually alive. A non-zero exit means the supervisor never acknowledged startup
  — you are still running and nothing was handed off. Read the error and either retry or
  run the command inline instead of assuming a monitor exists.
- The command after `--` is preserved argument-for-argument. Pass one quoted string
  (`-- 'just install && just check'`) and it runs verbatim as the shell command under
  the host's `/bin/sh -c`; pass several bare words (`-- just check`) and they are
  rejoined for you. Do not wrap the command in `bash -c '...'` or `sh -c '...'` — the
  host already runs it under a shell, so the wrapper is redundant and is the leading
  cause of monitor command misquoting (`sase monitor start` warns if you do it anyway).
- Only one monitor can be active per agent. An identical replay returns the existing
  monitor; a different request errors until the active monitor settles.
- Do not monitor interactive or TTY-requiring commands. Use monitors for batch commands,
  sleeps, deploy checks, and other noninteractive waits.
- Output is bounded and can rotate. Use `sase monitor show <id> --all-lines` or the log
  path from the follow-up prompt for retained output, not an assumption that every byte
  is preserved forever.
- `--reason` and `--next` text reaches the follow-up literally. A next action like
  `--next '#commit ...'` or `--next '%model:opus ...'` will not route or expand
  anything, but writing `#412` or a directive name in prose is safe. Use `-m/--model` to
  select the follow-up agent's model; `%model` text inside `--next` stays literal.
- Do not poll, sleep, or wait after `sase monitor start`; the starting agent is handed
  off and killed when running inside an agent.

## Sleep Or Wait

Use `sleep` as the monitored command when you need to wait for CI, a deploy, a rate
limit, or a scheduled time. Pair the wait with labels that name what is being waited on:

```bash
sase monitor start \
  --reason 'Wait for the CI run on PR #412 to finish' \
  --timeout 6m \
  --start-status 'SLEEPING FOR 300s' \
  --stop-status 'SLEPT FOR 300s' \
  --next 'Check the CI status for PR #412 with `gh pr checks 412`.' \
  -- sleep 300
```

Do not add `--idle-timeout` to an intentional quiet wait unless the sleep itself should
be treated as stalled.

## Fire And Forget

Omit `--next` when no follow-up agent should launch. The monitor still records the
command, reason, runtime, exit state, and retained output for later inspection:

```bash
sase monitor start \
  --reason 'Collect diagnostics for later inspection' \
  --timeout 20m \
  --start-status COLLECTING \
  --stop-status COLLECTED \
  -- ./collect-diagnostics.sh
```

## Useful Flags

- `--cwd DIR` runs the command from a specific directory. The default is the agent's
  workspace when SASE can resolve it, otherwise the current directory.
- `-p, --profile verify` supplies `TESTING` / `TESTED` labels and `--next-output auto`
  for verification commands. It does not authorize host completion by itself.
- `--agent NAME` targets a specific agent. Inside an agent, the current agent is the
  default -- including inside an epic phase lane and inside a promoted agent family, so
  no `--agent` is needed there either; outside an agent, pass it explicitly. (`--lane`
  still works as a deprecated alias.)
- `--label TEXT` controls the short row label shown in monitor lists.
- `-m, --model MODEL` — model or alias for the follow-up agent (`opus`, `opus@high`,
  `sonnet`, `codex/gpt-5`). Requires `--next`. Default: inherit the starter's model and
  reasoning effort. `%model` text inside `--next` stays literal; `--model` controls
  routing.
- `--tail-lines N` controls how many output lines are included when `--next-output tail`
  is used for the follow-up prompt, and caps raw output selected by `auto`.
- `-k, --checkpoint FILE` binds an authored YAML/JSON checkpoint by content digest. Use
  it for objective, constraints, findings, unresolved decisions, remaining work, source
  refs, or coverage; keep the next action in `--next`.
- `-P, --policy FILE` freezes a per-outcome policy before the monitor is created. It is
  mutually exclusive with `--profile`.
- `-f, --completion REF` binds a prepared host-completion intent from
  `sase final prepare`. The `verify` profile only supplies labels and evidence defaults;
  the completion ref is what authorizes successful host completion.
- `--idle-timeout DURATION` kills a command that produces no bytes for that duration.
  Omit it for valid quiet commands such as `sleep`.
- `-o, --next-output auto|tail|file|none` controls output handed to the follow-up.
  `auto` is the default and selects outcome-aware evidence, `tail` embeds the retained
  tail as fenced untrusted output, `file` names refs and log locators, and `none`
  includes only the outcome summary plus a `sase monitor show --all-lines` pointer.

## Inspect Or Stop

- `sase monitor list` shows active monitors by default; add `--all` to include history.
  An agent whose `--next` action did not launch (or launched degraded) is flagged with
  an amber `⚑` next to its state, so it is visible without `--json`.
- `sase monitor show <id>` shows details and the output tail; add `--follow` to stream
  until the monitor reaches a terminal state. A dropped follow-up prints a
  `Follow-up error` line; a degraded one prints a `Follow-up degraded` line.
- `sase monitor show <id> --diagnostics` prints selected failed-stage diagnostics;
  `--range START:END` prints a bounded retained raw-output byte range. Use
  `--format json` for machine-readable show output.
- `sase monitor resume <id> [-k FILE] [-m MODEL]` resumes an eligible terminal monitor's
  requested follow-up from the frozen result without rerunning the command. A checkpoint
  or model creates a manual-recovery branch only if delivery has not already been
  acknowledged.
- `sase monitor stop <id>` stops a running monitor. Stopped monitors do not launch their
  recorded follow-up agent.

## Follow-Up Context

When `--next` is set, the follow-up agent receives the previous conversation through
`#fork:<family>` — the whole family's transcript, not just the monitor's own turn, the
same shared shell substrate that gate shells fork through — plus the original reason,
the requested next action, and a command-run breakdown: outcome, exit code, elapsed
time, selected output policy, and the path to the retained captured log. The reason,
next action, table fields, and embedded output are wrapped as literal prompt text; only
the follow-up's routing prefix remains live. Omit `--model` to inherit the starter's
model and reasoning effort; pass `--model` to replace that inherited routing.

With `--next-output auto`, completed runs use facts and refs, failed runs prefer
diagnostic refs, and timeouts include a bounded raw tail. With `--next-output tail`, the
retained tail is fenced and labeled as untrusted command output. With
`--next-output file`, the follow-up gets refs and log locators instead of embedded
output. With `--next-output none`, it gets only the outcome summary and a
`sase monitor show --all-lines` pointer.

If the command fails or times out, the follow-up still launches. Its breakdown says
whether the total timeout or idle timeout fired. If the monitor is stopped manually or
marked `lost` after a reboot, the recorded follow-up does not launch.

The follow-up launch does not depend on the monitor's original workspace claim
transferring cleanly: if that claim is gone, the follow-up still launches (into a fresh
claim on the same workspace, or workspace `0` if that was taken), and the prompt says
which happened so the follow-up does not assume the command's artifacts are present.
Only when a follow-up genuinely cannot be launched is it dropped, and even then the
composed prompt is saved as a durable artifact rather than lost.
