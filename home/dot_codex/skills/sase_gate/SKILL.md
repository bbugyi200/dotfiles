---
name: sase_gate
description:
  Create beautiful, robust, and powerful custom notification gates on the fly. Use this as the easy way to propose
  commands for user confirmation, especially dangerous commands or commands the user asked to confirm before use.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_gate --reason "<one-line reason for using this skill>"
```

Use this skill when work must pause for a durable, command-backed user decision.

Create beautiful, robust, and powerful custom notification gates on the fly. A custom gate is the easy way to propose
commands for confirmation before they run: for example, a dangerous or irreversible command, a production change, or any
command the user explicitly asked to approve first. Use `/sase_questions` instead when you only need an answer and no
reviewed command should execute.

## Design The Gate

- Give the notification a fitting single-glyph icon. Examples: `🛡️` for a safety check, `🚀` for a deployment, `🧹` for
  cleanup, or `🔐` for an access change.
- Give every terminal choice its own clear label, command, and fitting icon such as `✅` for approve, `✋` for reject,
  or `⏸️` for defer. Even a reject choice needs an owned command; use a no-op command that emits a JSON result.
- Put independently selectable, ORable follow-up commands in `extras`. Each extra has its own icon and
  `default_selected` value. The terminal choice runs first, then selected extras run in their authored order.
- Set each choice's `feedback` to `disabled`, `optional`, or `required`. Custom gates default to `optional`, but write
  the mode explicitly so the user-facing contract is obvious.
- Set `gate_timeout_seconds` when waiting forever would be unsafe. Omit it only when the request should remain pending
  until it is answered or cancelled.

Command `argv` arrays are executed without a shell. Their first element must name an executable `command` resource in
the bundle. A command receives the choice input as JSON on stdin and must print exactly one JSON value on stdout;
diagnostics belong on stderr. A terminal command's output must satisfy its `result_schema`.

## Author The Request

Write the complete request to a JSON file. This example asks permission to restart a service and offers two independent
post-restart commands:

```json
{
  "schema_version": 1,
  "kind": "custom",
  "producer": {
    "agent": "my-agent"
  },
  "payload": {
    "intent": "Restart the example service after its configuration changed",
    "target": "example.service"
  },
  "presentation": {
    "icon": "🚀",
    "sender": "deployment-confirmation",
    "notes": ["Restart example.service now?", "Select any follow-up checks you also want to run."],
    "tags": ["deployment", "confirmation"]
  },
  "choices": [
    {
      "id": "restart",
      "label": "Restart service",
      "icon": "✅",
      "feedback": "optional",
      "command": {
        "argv": ["commands/restart"]
      },
      "input_schema": {
        "type": "object"
      },
      "result_schema": {
        "type": "object",
        "required": ["status"],
        "properties": {
          "status": { "const": "restarted" }
        }
      },
      "extras": [
        {
          "id": "verify",
          "label": "Verify service health",
          "icon": "🧪",
          "default_selected": true,
          "command": {
            "argv": ["commands/verify"]
          }
        },
        {
          "id": "audit",
          "label": "Write an audit record",
          "icon": "📝",
          "default_selected": false,
          "command": {
            "argv": ["commands/audit"]
          }
        }
      ]
    },
    {
      "id": "reject",
      "label": "Do not restart",
      "icon": "✋",
      "feedback": "required",
      "command": {
        "argv": ["commands/reject"]
      },
      "input_schema": {
        "type": "object"
      },
      "result_schema": {
        "type": "object",
        "required": ["status"],
        "properties": {
          "status": { "const": "rejected" }
        }
      }
    }
  ],
  "resources": [
    {
      "path": "commands/restart",
      "role": "command",
      "content": "#!/bin/sh\nset -eu\nsystemctl --user restart example.service\nprintf '{\"status\":\"restarted\"}\\n'\n"
    },
    {
      "path": "commands/verify",
      "role": "command",
      "content": "#!/bin/sh\nset -eu\nsystemctl --user is-active example.service >/dev/null\nprintf '{\"status\":\"healthy\"}\\n'\n"
    },
    {
      "path": "commands/audit",
      "role": "command",
      "content": "#!/bin/sh\nset -eu\nprintf '%s\\n' 'example.service restart approved' >> \"$HOME/.local/state/example-audit.log\"\nprintf '{\"status\":\"recorded\"}\\n'\n"
    },
    {
      "path": "commands/reject",
      "role": "command",
      "content": "#!/bin/sh\nprintf '{\"status\":\"rejected\"}\\n'\n"
    }
  ],
  "gate_timeout_seconds": 900,
  "auto": false
}
```

For larger commands, set a resource's `source` to a script you authored instead of embedding `content`; use exactly one
of `source` or `content`. Keep command resources narrowly scoped to the action shown to the user.

## Create And Wait

Create the durable gate and save its stable descriptor:

```bash
sase notify create --gate < gate-request.json > gate-descriptor.json
```

Read `request_id` and `kind` from that descriptor, then wait mechanically:

```bash
sase notify wait --id <request-id> --kind custom --json
```

`sase notify wait` honors the request timeout. Its optional `--timeout` can shorten that deadline. If the rest of your
work does not depend on the answer, proceed detached after creation instead of waiting; keep the descriptor as the
durable handoff.

## Handle The Result

The wait result has `status` (`answered`, `cancelled`, or `timeout`), `choice_id`, `selected_extra_ids`, `feedback`, and
`response_path`. An answered result tells you exactly which terminal choice ran, which ORable extras the user selected,
and what feedback they supplied. Respect cancellation and timeout as terminal outcomes; do not run the proposed action
through another path.

Never poll bundle files directly. Never run bundle commands by hand. Creation hashes every owned command and the shared
executor verifies and runs the selected commands. Automatic resolution is forbidden for custom gates: never enable
`auto` or use an automatic-resolution path to bypass the user's decision.
