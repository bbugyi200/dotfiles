---
type: reference
parent: AGENTS.md
description:
  Tailnet machines (athena, apollo, mac) - Tailscale SSH access, users, and the
  chezmoi-managed ~/.ssh/config convention.
---

# Tailnet Machines

All of Bryan's personal machines join the Tailscale tailnet `tail297af1.ts.net` and are
reachable from each other over SSH via that tailnet.

| SSH alias | Tailscale name       | OS    | SSH user | Machine                        |
| --------- | -------------------- | ----- | -------- | ------------------------------ |
| `athena`  | `athena`             | Linux | `bryan`  | Bryan's home server            |
| `apollo`  | `apollo`             | Linux | `bryan`  | DigitalOcean rendezvous server |
| `mac`     | `kellys-macbook-pro` | macOS | `bbugyi` | Kelly's MacBook Pro            |

- The MacBook (`mac`) is offline unless it is powered on with its lid open. Treat SSH to
  it as best-effort and expect connection timeouts otherwise.
- `apollo` is also reachable at its DigitalOcean public IP through the `apollo-do`
  alias, which keeps working when Tailscale is down.

## SSH Config Convention

Every tailnet machine configures SSH access to the other tailnet machines through
chezmoi:

- The host blocks above live in the chezmoi-managed `~/.ssh/tailnet.conf`.
- A chezmoi `run_onchange` script ensures `Include tailnet.conf` is present at the top
  of `~/.ssh/config` on each tailnet machine, creating that file if missing.
- Add or change tailnet host blocks only in the chezmoi source
  (`private_dot_ssh/private_tailnet.conf`), never directly in a machine's
  `~/.ssh/config`; each machine picks up changes on its next `chezmoi update` or
  `chezmoi apply`.
