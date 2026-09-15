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
  diagnostics; use `full` only when the complete output is necessary and safe.
- Set `machine` for remote targets. Leave it out for the local host.
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

The command creates a reviewed sudo gate and intentionally ends your current turn. Bryan
authenticates only on a real terminal handed to `/usr/bin/sudo`/PAM. A successor agent
receives the structured ledger with the authentication outcome, per-command statuses,
exit codes, durations, and bounded output allowed by `output_to_agent`.
