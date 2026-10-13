---
name: sase_project
description: >-
  Inspect and manage SASE projects with `sase project` (list, add, create, show,
  current, set-current, enable, disable, alias, suggest). Use when you need the set of
  enabled projects, the current project, one project's lifecycle record, or machine-
  readable project data — e.g. to fan out one agent per enabled project.
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
- `sase project current` prints the current project derived from the VCS macro MRU head,
  colored with that project's accent. Add `--json` for machine-readable data.

## Suggest Projects

- `sase project suggest [PROVIDER] [-a|--all] [-j|--json] [-o|--owner OWNER]... [-r|--refresh]`
  ranks the repositories worth adding as projects, grouped as `RESUME`,
  `ON THIS MACHINE`, `SUGGESTED`, `LINKED TO YOUR PROJECTS`, and `DISABLED PROJECTS`.
  Discovery is cache-first per owner and read-only — nothing is cloned, created, or
  registered — so agents may call it freely.
- `sase project suggest --json` emits the machine-readable candidate document
  (`schema_version`, per-provider `owners`, `groups`, and `hidden` counts, plus
  `search_only` rows with `--all`). Prefer it when selecting a repository to add
  programmatically.

## Add An Existing Repository

- Preview registration with `sase project add REF --check`. The check is read-only and
  reports identity allocation, checkout state, setup, blockers, and the apply argv.
- Apply with `sase project add REF --yes`, or confirm the plan in a terminal. New
  projects are enabled by default, and repeating the same command resumes an interrupted
  operation.
- Agents may preview and add with automatic setup disabled. Omit `--setup`; if human
  setup is needed, propose the exact `sase project add REF --setup --yes` command
  through `/sase_gate`.
- Human setup can mark the repository managed, commit the marker, and push the default
  branch. Afterward, a terminal may offer `sase init -p KEY`; sidecar creation still
  requires its own confirmation.

## Create A Repository

- Preview with `sase project create REF --check`. REF is `gh:OWNER/NAME`, `OWNER/NAME`,
  or `git:NAME`. The check is read-only and available to agents; it lists every provider
  option with default, value, and availability.
- Apply is human-only. Agents must not run `sase project create … --yes`. Propose the
  exact `sase project create … --yes` command through `/sase_gate`. An approved gate
  option (`SASE_GATE_COMMAND=1`) is allowed. `SASE_PROJECT_CREATE_BYPASS` is for humans,
  or when a user explicitly instructs it.
- Sugar `-d/--description` and `-v/--visibility` overlay `-O/--option KEY=VALUE`. Repeat
  the same command to resume an interrupted create.

## Manage Projects

- `sase project set-current <project>` promotes an enabled, launchable project to the
  VCS macro MRU head — the same write a launch on that project performs.
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
