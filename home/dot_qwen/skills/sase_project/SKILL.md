---
name: sase_project
description: >-
  Inspect and manage SASE projects with `sase project` (list, show, current, set-
  current, enable, disable, alias). Use when you need the set of enabled projects, the
  current project, one project's lifecycle record, or machine-readable project data —
  e.g. to fan out one agent per enabled project.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_project --reason "<one-line reason for using this skill>"
```

Use this skill to inspect project lifecycle records, the current project, manage project
state and aliases, or select projects for a multi-project workflow.

## Inspect Projects

- `sase project list` lists enabled projects by default. Use `--state disabled`,
  `--state sibling`, or `--state all` to select other lifecycle records.
- `sase project list --json` emits records whose key fields include `project_name`,
  `effective_project_name`, `state`, and `launchable`.
- `sase project show <project>` shows one project's state, aliases, workspace, active
  claims, launchability, and warnings. Add `--json` for machine-readable data.
- `sase project current` prints the current project derived from the VCS xprompt MRU
  head, colored with that project's accent. Add `--json` for machine-readable data.

## Manage Projects

- `sase project set-current <project>` promotes an enabled, launchable project to the
  VCS xprompt MRU head — the same write a launch on that project performs.
- `sase project enable <project>` enables a project.
- `sase project disable <project>` disables a project. It refuses projects with live
  work unless `--force` is passed.
- `sase project alias list [PROJECT] [--json]` inspects aliases; use `alias add`,
  `alias remove`, or `alias clear` to mutate them.

The system-managed `home` project cannot be mutated. The `sibling` state is an internal
backing record for configured linked repositories, not a user-facing project lifecycle
state.

## Fan Out Across Enabled Projects

Use `sase project list --json` to select enabled, launchable project records, then
request one `/sase_run` launch per project. Pair this skill with `/sase_repo` whenever
the current agent itself needs to read or modify files in another project's repository.
