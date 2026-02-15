# Problems with Generalizing gai for Claude Code + Git/GitHub

Critique of the design in `plans/gai_git_claude_plan.md` and its implementation so far.

---

## 1. The Fundamental Architectural Mismatch

The plan treats git+GitHub as a swap-in replacement for hg+Google code review, but the workflow models are fundamentally
different.

**Hg/Google model (what gai assumes):**

- You work on a local _bookmark_ (named commit). You `hg amend` it repeatedly.
- A CL is a _single mutable commit_. Amendments mutate it in-place.
- `hg upload tree` pushes for review. `hg mail` requests review. These are separate steps.
- Multiple workspaces (citc/fig) share the same repo state via a central server.

**Git/GitHub model:**

- You work on a _branch_ with _multiple immutable commits_. You push them.
- A PR is a _branch_ (series of commits), not a single mutable commit.
- `git commit --amend` rewrites history and requires `git push --force`. This is risky on shared branches.
- There's no concept of "workspaces" — you have one working tree (or worktrees, which are rudimentary by comparison).

The plan's Phase 5 acknowledges this but vastly underestimates the gap. The entire ChangeSpec COMMITS tracking system
(`1a`, `1b`, `2a` — tracking each amendment as a numbered entry) doesn't map to GitHub's model, where you'd typically
just push new commits.

---

## 2. Specific Things That Will Break (The Gaps)

### A. `bb_get_workspace` — Already broken

`running_field.py:546` directly calls `bb_get_workspace` via `subprocess.run()`. This is a Google-internal command for
managing citc/fig workspace shares (numbered workspaces 1-9). It was never abstracted into the VCS provider. The entire
workspace system (`get_workspace_directory()`, `get_workspace_and_suffix()`) assumes this command exists.

Files affected: `running_field.py`, `ace/tui/widgets/file_panel.py:374`, and every caller of `get_workspace_directory()`
— which is basically the entire ace TUI and axe scheduler.

### B. `run_shell_command` calls that bypass VCS provider

These files call Google-internal shell commands directly, bypassing the VCS abstraction entirely:

| File                   | Command                    | What it does                         |
| ---------------------- | -------------------------- | ------------------------------------ |
| `chat_history.py:24`   | `branch_or_workspace_name` | Get context for chat file naming     |
| `prompt_history.py:33` | `branch_or_workspace_name` | Get context for prompt file naming   |
| `prompt_history.py:45` | `workspace_name`           | Get workspace name                   |
| `shared_utils.py:148`  | `workspace_name`           | Get project name                     |
| `shared_utils.py:203`  | `bam 3 ...`                | Audio notification (Google-internal) |
| `main/utils.py:18`     | `workspace_name`           | Get project name from CLI            |
| `crs_workflow.py:58`   | `critique_comments`        | Get code review comments             |

These will all crash with `FileNotFoundError` outside Google.

### C. `ace/tui/actions/base.py` — Direct `bb_hg_update` subprocess calls

Lines 455-456 and 530-531 call `subprocess.run(["bb_hg_update", ...])` directly — not through the VCS provider. This is
in the TUI's checkout-to-workspace and open-tmux-at-workspace actions. The VCS abstraction was never wired in here.

Similarly, `ace/tui/actions/axe.py:270` does `subprocess.run(["bb_hg_update", cl_name], ...)` directly.

### D. `p4head` hardcoded as the default checkout target

`ace/operations.py:135`, `ace/restore.py:174`, `ace/tui/actions/proposal_rebase.py:331` all use the literal string
`"p4head"` as a revision target. In hg, `p4head` is a bookmark pointing to the latest synced Perforce revision. Git has
no equivalent — you'd need `origin/main` or `HEAD` of the default branch. This isn't just a naming issue; the concept of
"the latest sync point" is different.

### E. `p4 findreviewers` — No GitHub equivalent

`ace/mail_ops.py:100-126` calls `p4 findreviewers` to suggest code reviewers. GitHub has no equivalent CLI command.
You'd need to use the GitHub API (CODEOWNERS file, or `gh api` to look at blame/history). The plan lists this as
`find_reviewers() -> raises NotImplementedError` in the git provider, but `mail_ops.py` doesn't handle
`NotImplementedError` — it'll crash.

### F. CL URL format hardcoded to `http://cl/<number>`

`ace/scheduler/checks_runner.py:104-105` and `ace/tui/actions/clipboard.py:383-384` use
`re.match(r"https?://cl/(\d+)", cl_url)` to parse CL URLs. GitHub PR URLs look like
`https://github.com/org/repo/pull/123`. The code will fail to match and silently skip these.

### G. `critique_comments` shell command (CRS workflow)

`crs_workflow.py:58` calls `critique_comments` — a Google-internal tool for fetching code review comments. The entire
CRS (Critique Review System) workflow has no GitHub equivalent and will fail completely.

### H. `hg fix` and `hg upload tree` in commit workflow

`commit_workflow/workflow.py` calls `provider.fix()` and `provider.upload()` after creating a commit. The git provider
returns `(True, None)` for both — silent no-ops. This means after `gai commit` in a git repo:

- No auto-formatting runs (the `hg fix` equivalent would be running pre-commit hooks or formatters)
- No upload happens (you'd need `git push -u origin <branch>`)

The user has to know these are no-ops and do them manually.

### I. The `bb_hg_presubmit` and `bb_hg_lint` default hooks

`ace/constants.py:10-11` hardcodes `"!$bb_hg_presubmit"` and `"$bb_hg_lint"` as default hooks. These are Google-internal
commands. In a git repo, these would need to be replaced with project-specific CI checks, but there's no mechanism for
that.

### J. Workspace numbering system (100-199 range)

The axe scheduler uses workspace numbers 100-199 for concurrent hook execution. Each workspace is obtained via
`bb_get_workspace`. Git has `git worktree` but:

- Worktrees don't auto-create numbered copies
- There's no `bb_get_workspace` equivalent
- The entire `RunnerPool` workspace claim/release system depends on this

---

## 3. Design-Level Problems

### A. The abstraction is at the wrong level

The `VCSProvider` ABC tries to abstract individual VCS _commands_ (`checkout`, `diff`, `amend`). But the real
differences are at the _workflow_ level:

- In hg, "mail a CL" = `hg mail`. In git, "mail a CL" = `git push` + `gh pr create` + maybe set reviewers. These are
  fundamentally different operations, not just command substitutions.
- In hg, "amend" mutates a commit. In git, "amend" = `git commit --amend` + `git push --force`, which is destructive and
  has different failure modes.
- The concept of "stacked CLs" (parent/child) maps to stacked PRs in git, which are notoriously painful and require
  tools like `git-town` or `ghstack`.

A better abstraction would be at the **workflow** level: `create_change()`, `update_change()`, `submit_for_review()`,
`land_change()`.

### B. The ChangeSpec model assumes a CL-centric worldview

ChangeSpec's STATUS transitions (`WIP -> Drafted -> Mailed -> Submitted`) don't map cleanly:

- **"Mailed"** in Google = sent for code review. In GitHub, the nearest equivalent is "PR opened" — but creating a PR
  also involves choosing base branch, writing a PR body, setting reviewers. `Mailed` conflates all of these.
- **"Submitted"** in Google = landed by the review system. In GitHub, PRs are merged (which could be merge commit,
  squash, or rebase). The semantics are different.
- There's no GitHub equivalent of **"Drafted"** (Google's "ready to mail but not mailed yet"). GitHub draft PRs are
  different — they're already pushed remotely.

### C. The COMMITS suffix tracking system is Google-specific

The COMMITS section tracks every amendment with suffixes like `(@: agent-PID-timestamp)` for running agents and
`($: PID)` for running processes. This is deeply tied to Google's multi-workspace concurrent amendment model. In git,
you don't amend repeatedly in separate workspaces — you push commits to a branch.

### D. ClaudeCodeProvider invocation model is wrong for a Claude Code-developed project

The plan uses `claude -p --dangerously-skip-permissions` to invoke Claude as a subprocess that takes a prompt on stdin
and returns text on stdout. But for a project "developed primarily by Claude Code":

- Claude Code is the _outer loop_, not something you shell out to. You'd be running Claude Code, which runs gai, which
  shells out to Claude Code again. This is circular.
- The `--dangerously-skip-permissions` flag is a significant security concern for an open-source project.
- The streaming model (read stdout in real-time) assumes Claude produces a single text response, but Claude Code's
  actual output is tool calls, thinking, and responses interleaved.

### E. The test suite tests mocks, not behavior

167 test files and 2,857 tests sounds impressive, but the VCS provider tests almost entirely mock `subprocess.run`.
There are only 14 integration tests that actually run git commands, and 0 that run Claude Code. This means:

- You can't know if `git rebase --onto` actually works correctly in the edge cases
- The mock-based tests will happily pass even if the git commands are wrong
- There's no test that exercises the full commit -> amend -> mail workflow on a real git repo

---

## 4. What Would Actually Need to Change

For this to work on a real GitHub project developed by Claude Code:

1. **Replace the workspace system entirely** — Git worktrees or just single working directory
2. **Rewrite `mail_ops.py`** — GitHub PR creation is fundamentally different from `hg mail`
3. **Abstract 6+ `run_shell_command` call sites** — `branch_or_workspace_name`, `workspace_name`, `critique_comments`,
   `bam`
4. **Replace all direct `subprocess.run(["bb_hg_*", ...])` calls** — at least 3 call sites in the TUI
5. **Replace `p4head`** with `origin/main` or configurable default branch
6. **Replace CL URL parsing** with GitHub URL parsing
7. **Replace default hooks** (`bb_hg_presubmit`, `bb_hg_lint`) with configurable hooks
8. **Rethink the COMMITS tracking model** for git's immutable-commit model
9. **Reconsider the LLM invocation model** — shelling out to `claude` from within a Claude Code session is odd
10. **Add real integration tests** that exercise git workflows end-to-end

The plan's phased approach is reasonable _in structure_, but it underestimates the scope of Phase 5-6 by roughly 3-5x.
The VCS provider abstraction (Phase 3-4) provides the illusion that the migration is done, while the real work — making
the _workflows_ and _UI_ actually function — is where the bulk of the effort lies.
