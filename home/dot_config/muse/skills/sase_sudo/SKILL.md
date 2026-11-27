---
name: sase_sudo
description:
  Request reviewed privileged execution through a typed sudo gate instead of running raw
  sudo.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_sudo --reason "<one-line reason for using this skill>"
```

Use this skill when a task truly needs a privileged command: package installs,
system-service changes, edits under root-owned paths, sysctl/sudoers changes, or the
same operations on a remote machine.

## Rules

- Never ask Bryan for a password, passphrase, OTP, or other PAM answer anywhere. Do not
  put credential material or its length, digest, timing, or attempt count in prompts,
  files, gate inputs, command args, stdin, environment, logs, or notes.
- Never run raw `sudo`, `doas`, `pkexec`, `su`, or a nested privilege helper from Bash.
  The reviewed `sase sudo request` flow is the only agent path for privileged execution.
- Do every non-root step first. Inspect state, build files, render configs, and compute
  exact argv arrays before asking for privilege.
- Prefer a non-root alternative whenever it will solve the problem. If root is
  unavoidable, say why in the request.
- Batch the privileged work into one request. Give every command a stable `id`, exact
  `argv`, and a one-line `why`.
- Set the top-level `"output_to_agent": "none"` for secret-adjacent commands or any
  command whose output should not enter the next model context. Use `tail` for ordinary
  diagnostics; use `full` only when the complete output is necessary and safe. `full` is
  still bounded by a shared ~60 KiB settlement budget across every selected command, so
  prefer targeted commands (for example `nft list chain ...` or filtered `ss`) over
  whole-system dumps.
- Set `machine` for remote targets. Leave it out for the local host.
- Executables are snapshotted and write-guarded on the host that will run them. Use
  absolute paths that exist on that target. Do not wrap a target-only binary in an
  interpreter script so the request can be created from another machine.
- The target must be reachable over SSH, with sase upgraded far enough to advertise
  `executable_snapshot`, when the request is created. An unreachable or outdated target
  fails `sase sudo request`; retry when the host is online.
- On macOS targets, `Operation not permitted` from a root command is TCC (the SSH
  session lacks Full Disk Access), not SIP. Stop and ask Bryan to enable System Settings
  → General → Sharing → Remote Login ⓘ → "Allow full disk access for remote users". Do
  not work around the denial. Pre-flight with
  `ssh -o BatchMode=yes <host> head -c1 '/Library/Application Support/com.apple.TCC/TCC.db'`;
  `Operation not permitted` means Full Disk Access is missing.
- The request stays reviewable for `gate_timeout_seconds` (default one day). If nobody
  approves in that window, the gate times out, no successor runs, and the session ends.
  Set a shorter window only when the batch would be unsafe to run later. Top-level
  `timeout_seconds` is only the default per-command timeout; it never shortens the
  review window.
- If `sase sudo request` is unavailable or disabled, report that blocker. Do not fall
  back to raw sudo.

## Request

Write one JSON object to `sase sudo request` on stdin:

```bash
sase sudo request <<'JSON'
{
  "reason": "Install the reviewed package update on apollo",
  "machine": "apollo",
  "run_as": "root",
  "cwd": "/",
  "commands": [
    {
      "id": "apt-update",
      "argv": ["/usr/bin/apt-get", "update"],
      "why": "refresh the package index before installing the update"
    },
    {
      "id": "apt-install",
      "argv": ["/usr/bin/apt-get", "install", "-y", "tailscale"],
      "why": "install the reviewed package update",
      "timeout_seconds": 600
    }
  ],
  "stop_on_failure": true,
  "output_to_agent": "tail",
  "next": {
    "prompt": "Read the sudo ledger, verify the installed tailscale version, and continue."
  }
}
JSON
```

Run `sase sudo request` in the foreground and wait for it to exit on its own. Never
invoke it with a yield window, a background flag, or an early-return timeout. Never wrap
the command in `timeout`, a pipe, or a background job. Read the JSON descriptor and
check its `status` before deciding what happens next.

When the descriptor says `"status": "staged"`, nothing starts until this turn ends.
Finish through `/sase_final` so host finalizers settle before the sudo gate is
published. Do not wait for your own staged gate; it starts after the turn ends. Other
gates may still be waited on.

When the descriptor has no staged status and `auto_resolution.state` is `resolved`, the
gate resolved automatically and this process continues. If it does not report staged and
did not auto-resolve, the gate was not created — read the output and continue or retry.
An error, unexpected output, timeout, or empty result does not mean the gate was
created.

Bryan authenticates only on a real terminal handed to `/usr/bin/sudo`/PAM. A successor
agent receives the structured ledger with the authentication outcome, per-command
statuses, exit codes, durations, and bounded output allowed by `output_to_agent`.
