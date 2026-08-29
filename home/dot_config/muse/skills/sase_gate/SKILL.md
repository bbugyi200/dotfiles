---
name: sase_gate
description:
  Create beautiful, robust, and powerful custom notification gates on the fly. Use this
  as the easy way to propose commands for user confirmation, especially dangerous
  commands or commands the user asked to confirm before use.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_gate --reason "<one-line reason for using this skill>"
```

Use this skill when work must pause for a durable, command-backed user decision.

Create beautiful, robust, and powerful custom notification gates on the fly. A custom
gate is the easy way to propose commands for confirmation before they run: for example,
a dangerous or irreversible command, a production change, or any command the user
explicitly asked to approve first. Use `/sase_questions` instead when you only need an
answer and no reviewed command should execute.

## Design The Gate

Start with one option query that reads like the decision:

```text
(restart AND verify) OR reject
```

Each `OR` branch is a mutually exclusive way to resolve the gate. A singleton branch is
one button that runs its option. An `AND` branch is a group of independently selectable
options with one submit button; the user may submit any non-empty subset. `AND` binds
tighter than `OR`, and every option id must appear exactly once in the query and exactly
once in the `options` list.

- Give the notification a fitting single-glyph icon. Examples: `🛡️` for a safety check,
  `🚀` for a deployment, `🧹` for cleanup, or `🔐` for an access change.
- Set `presentation.title` to the one-line decision headline: for example
  `"Restart example.service"`, not `"Confirmation needed"`. It is stripped, must be a
  single line, and must be at most 120 characters.
- Give every option its own clear label, command, and fitting icon such as `✅` for
  approve, `✋` for reject, or `⏸️` for defer. Even a reject option needs an owned
  command; use a no-op command that emits a JSON result.
- Set `default_selected` on members of an `AND` branch. It defaults to `true`; singleton
  branches ignore it.
- Declare exactly one complete query branch as `primary_branch`, with its option ids in
  canonical query order. Enter submits this branch from the review modal; for an `AND`
  branch it preserves any options the user toggled with Space.
- Add a `groups` entry when an `AND` branch's submit button should differ from its first
  option. Match the branch by its option ids, then configure the submit `label` and
  `icon`.
- Set every option's `feedback` to `disabled`, `optional`, or `required`. Custom gate
  options default to `optional`, but write the mode explicitly so the user-facing
  contract is obvious. An `AND` selection uses the strongest feedback mode among the
  selected options.
- Set `gate_timeout_seconds` when waiting forever would be unsafe. Omit it only when the
  request should remain pending until it is answered or cancelled.
- Set `presentation.panel` when the notification belongs in a named panel tab. Panel
  names are stripped, lowercased, limited to 32 characters, and may contain lowercase
  letters, digits, underscores, and hyphens. Reserved names — `errors`, `gates`,
  `general`, `hitl`, `muted`, `snoozed`, and any name beginning with `__` — are all
  rejected. Declaring `panel` requires also declaring `presentation.panel_icon`: one
  emoji or glyph identifying that tab at a glance. A gate that names a tab is the thing
  introducing that tab to the user, so it is the thing responsible for saying what the
  tab looks like.
- Set `presentation.origin_agent` to the agent the gate was filed on behalf of. It is an
  attribution label rather than a routing identity, so remote agent names are valid even
  when the local host has never seen them.
- Set `presentation.chip` when the gate's subject should carry a one-glyph identity chip
  (glyph, short label, optional `#RRGGBB` color) on the toast, the notification row, the
  gate detail pane, and the review modal. The glyph is one grapheme; the label is
  stripped, single-line, at most 32 characters, and free of control characters. A
  declared chip is projected into `action_data` as `gate_chip_glyph`, `gate_chip_label`,
  and `gate_chip_color` (the colour key is omitted when there is no colour). Do not
  write those keys through `presentation.action_data`. Every gate whose subject is a
  typed task bead already declares this chip from the presentation frozen at creation.

`presentation.title`, `presentation.icon`, and at least one non-blank
`presentation.notes` line are **required** for every custom gate — creation fails with
`missing_presentation` otherwise. `presentation.panel_icon` is likewise **required**
whenever `presentation.panel` is declared. Everything you put in `title`, `icon`,
`notes`, option labels, option icons, and command paths is rendered directly in the
notification panel's detail pane, so those fields are the user's whole view of the
decision: write them for the reviewer, not for yourself.

Command `argv` arrays are executed without a shell. Their first element must name an
executable `command` resource in the bundle. A command receives the gate input as JSON
on stdin and must print exactly one JSON value on stdout; diagnostics belong on stderr.
Every command's output must satisfy its option's `result_schema`.

## Declare Inputs And Actions

When an option's command needs a real value — not just free-text feedback — declare it
under that option's `inputs`, a closed, typed vocabulary that compiles into the option's
`input_schema` at creation. Never invent a way to smuggle a value through `argv`; the
command always reads its input as JSON on stdin. Each field needs an `id` (the JSON
property name, `^[a-z][a-z0-9_]*$`), a `label`, and a `type`: `word`, `line`, `text`,
`path`, `agent`, `int`, `bool`, `float`, or `enum` (which also requires a non-empty
`choices` list of strings or `{value, label}` objects). Mark a field `required` when the
command cannot run without it, `secret: true` when its value must never be written to
durable audit data unredacted, and `repeatable: true` when the command accepts a list.
An option declaring neither `inputs` nor `input_schema` takes no input at all —
`sase gate create` rejects any option whose declared schema could never be satisfied by
a real submission, naming the offending property, so an unanswerable gate fails loudly
at creation instead of dying silently on first submission.

A gate may also declare repeatable **actions** under `operations`: commands the reviewer
can run any number of times without answering the gate, useful for a diff view, a health
probe, or anything else that helps them decide before committing to an option. Give each
one a stable `id`, `kind: "run_command"`, a `label`, and a `command`; its stdout must be
one JSON value, and the reviewer sees its `summary` (a one-line toast) and `body`
(rendered per the declared `display`).

## Author The Request

Write the complete schema-version 3 request to a JSON file. This example asks permission
to restart a service, lets the user include or omit the health check, and provides a
separate rejection path:

```json
{
  "schema_version": 3,
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
    "title": "Restart example.service",
    "panel": "deployments",
    "panel_icon": "🚀",
    "sender": "deployment-confirmation",
    "notes": ["Restart example.service now?", "Select whether to verify it afterward."],
    "tags": ["deployment", "confirmation"],
    "chip": { "glyph": "🚀", "label": "deploy", "color": "#5FD75F" }
  },
  "query": "(restart AND verify) OR reject",
  "primary_branch": ["restart", "verify"],
  "options": [
    {
      "id": "restart",
      "label": "Restart service",
      "icon": "🚀",
      "default_selected": true,
      "feedback": "optional",
      "command": {
        "argv": ["commands/restart"]
      },
      "inputs": [
        {
          "id": "mode",
          "label": "Restart mode",
          "type": "enum",
          "required": true,
          "choices": [
            { "value": "quick", "label": "Quick restart" },
            { "value": "full", "label": "Full restart (clears cache)" }
          ]
        }
      ],
      "result_schema": {
        "type": "object",
        "required": ["status"],
        "properties": {
          "status": { "const": "restarted" }
        }
      }
    },
    {
      "id": "verify",
      "label": "Verify service health",
      "icon": "🧪",
      "default_selected": true,
      "feedback": "disabled",
      "command": {
        "argv": ["commands/verify"]
      },
      "result_schema": {
        "type": "object",
        "required": ["status"],
        "properties": {
          "status": { "const": "healthy" }
        }
      }
    },
    {
      "id": "reject",
      "label": "Do not restart",
      "icon": "✋",
      "feedback": "required",
      "command": {
        "argv": ["commands/reject"]
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
  "groups": [
    {
      "options": ["restart", "verify"],
      "label": "Restart service",
      "icon": "🚀"
    }
  ],
  "operations": [
    {
      "id": "show_status",
      "kind": "run_command",
      "label": "Show current status",
      "icon": "🔍",
      "key": "s",
      "command": { "argv": ["commands/show_status"] },
      "result_schema": {
        "type": "object",
        "required": ["summary"],
        "properties": { "summary": { "type": "string" } }
      },
      "display": "text"
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
      "path": "commands/reject",
      "role": "command",
      "content": "#!/bin/sh\nprintf '{\"status\":\"rejected\"}\\n'\n"
    },
    {
      "path": "commands/show_status",
      "role": "command",
      "content": "#!/bin/sh\nset -eu\nstate=$(systemctl --user is-active example.service || true)\nprintf '{\"summary\":\"example.service is %s\"}\\n' \"$state\"\n"
    }
  ],
  "gate_timeout_seconds": 900,
  "auto": false
}
```

`show_status` never answers the gate and may be run any number of times before the
reviewer decides. It declares no `targets`, so it must not rewrite any resource; an
action that does need to rewrite one lists that resource's path under `targets`, or the
run is rejected after the fact for touching something it never declared.

For larger commands, set a resource's `source` to a script you authored instead of
embedding `content`; use exactly one of `source` or `content`. Keep command resources
narrowly scoped to the action shown to the user.

## Declare The `shell` Block

A gate you create from inside an agent should almost always be a **gate shell**: a
named, non-LLM member of your agent family that publishes the decision, outlives you,
runs the commands the reviewer selects, and hands their typed outcome to the next family
member. Add a `shell` block to make your gate one:

```json
{
  "shell": {
    "pending_status": "CONFIRM",
    "settled_status": "CONFIRMED",
    "workspace": "inherit",
    "next": {
      "prompt": "Verify the reclaimed space and close the tracking bead.",
      "output": ["results"],
      "fork": "family"
    },
    "branches": {
      "reject": { "prompt": null }
    }
  }
}
```

| Field            | Meaning                                                      | Default                            |
| ---------------- | ------------------------------------------------------------ | ---------------------------------- |
| `suffix`         | Family suffix for the gate-shell member                      | allocated: `--gate`, `--gate-0`, … |
| `pending_status` | Row status while awaiting a human (≤20 chars)                | `GATE`                             |
| `settled_status` | Row status after settling                                    | `GATED`                            |
| `accent`         | Pin the status-pair colour (`#RRGGBB`) instead of hashing it | hashed                             |
| `workspace`      | `inherit` \| `release`                                       | `inherit`                          |
| `next.prompt`    | Literal "Your next action" text; `null` = no follow-up       | `null`                             |
| `next.output`    | `none` \| `results` \| `tail` \| `file`, or a list           | `["results"]`                      |
| `next.fork`      | `family` \| `shell` \| `none`                                | `family`                           |
| `next.model`     | Model/alias for the follow-up agent                          | inherit yours                      |
| `branches.<key>` | Override, keyed by `+`-joined option ids in query order      | —                                  |

`branches` is one keyed map, not a separate mechanism for the unanswered axis: the same
map also takes the reserved keys `timeout`, `stopped`, and `failed` for when no branch
was selected. An absent key means no follow-up for that outcome — exactly the example
above, which reads no differently after a reject than a monitor does after it stops.

`next.output: "results"` is the default for a reason: every selected option's command
already returns `result_schema`-validated JSON, which is strictly better data to hand
the follow-up than a raw stdout tail. Use `tail` only for a chatty command whose text
output itself matters, and compose the two freely. There is no templating: the composed
prompt's only instruction is the literal `next.prompt` text under "Your next action";
everything else — the decision, the branches, the reviewer's note, the results — is
fenced, labelled, untrusted data, exactly like a monitor's output. Never rely on
interpolating anything into `next.prompt` yourself.

Every existing built-in gate keys its `next` by branch because each outcome needs a
different next step:

| Branch           | `next`                              |
| ---------------- | ----------------------------------- |
| `approve+commit` | implementation prompt, `fork: none` |
| `feedback`       | replan prompt, `fork: family`       |
| `reject`         | `null` — the family simply ends     |

Write your own `next` and `branches.<key>.{prompt,output,fork,model,status,accent}` the
same way: one outcome, one follow-up policy.

## Create The Gate Shell, Then Stop

Create the durable gate:

```bash
sase gate create --shell \
  --next 'Verify the reclaimed space and close the tracking bead.' \
  --next-output results --next-fork family \
  < gate-request.json > gate-descriptor.json
```

`--shell`, `--shell-status`, `--shell-stop-status`, `--next`, `--next-fork`,
`--next-model`, and `--next-output` are CLI shortcuts for the same `shell`/`next`
fields; everything is also expressible in the JSON request body, which is what keeps
this skill declarative.

**Print the descriptor, then stop. Do not wait, poll, or keep working.** Creating a gate
shell ends your turn: the runner hands off to the gate shell and kills your process
immediately after the descriptor prints. There is nothing after this for you to do —
`sase gate wait` is rejected outright for a shell gate under an agent runner, with a
message pointing back at `--shell`, because waiting is exactly the blocking behaviour a
gate shell exists to remove. (It still works for non-agent scripts and tests answering a
non-shell gate.) The reviewer's decision and its command results reach the _next_ family
member automatically, composed into their prompt's labelled sections per the `next`
policy above. Never poll bundle files directly. Never run bundle commands by hand.

If your gate resolves via `"auto": true` before creation even returns, none of this
costs you a hand-off: creation settles it synchronously and your own process continues
as the successor in-process, at the price of one agent, exactly as today. Automatic
resolution is forbidden for custom gates that exist to get a _human_ decision: never
enable `auto` to bypass the reviewer's choice yourself.
