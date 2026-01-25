# GAI (Google AI - LangGraph Workflow Runner)

AI-assisted change list (CL) management for Mercurial workflows. GAI provides an interactive TUI for managing ChangeSpecs, a background daemon for continuous monitoring, AI-powered workflows, and a powerful query language for filtering CLs.

## Table of Contents

- [Installation & Setup](#installation--setup)
- [CLI Commands Reference](#cli-commands-reference)
- [Ace TUI Reference](#ace-tui-reference)
- [Axe Daemon Reference](#axe-daemon-reference)
- [ChangeSpec Format](#changespec-format)
- [Query Language Reference](#query-language-reference)
- [Workflows Reference](#workflows-reference)
- [Configuration Reference](#configuration-reference)
- [Architecture Overview](#architecture-overview)
- [Data Storage Reference](#data-storage-reference)
- [Suffix System Reference](#suffix-system-reference)

## Installation & Setup

### Requirements

- Python 3.10+
- Mercurial (hg)
- Required Python dependencies (see `pyproject.toml`)

### Configuration

- **Config file**: `~/.config/gai/gai.yml`
- **Project storage**: `~/.gai/projects/`
- **Chat history**: `~/.gai/chats/`
- **Axe state**: `~/.axe_state/`

## CLI Commands Reference

| Command | Purpose |
|---------|---------|
| `gai ace [query]` | Interactive TUI for managing ChangeSpecs |
| `gai axe` | Background daemon for status monitoring |
| `gai commit <cl_name> [file_path]` | Create Mercurial commits with metadata |
| `gai amend [note]` | Amend commits with HISTORY tracking |
| `gai restore [name]` | Restore reverted ChangeSpecs |
| `gai revert <name>` | Revert and archive ChangeSpecs |
| `gai search <query>` | Search ChangeSpecs (plain or rich output) |
| `gai xprompt [prompt]` | Expand gai references in prompts |
| `gai run <workflow>` | Execute workflows |

### gai ace

Interactive TUI for navigating and managing ChangeSpecs.

```bash
gai ace [query]                    # Open TUI with query filter
gai ace                            # Uses last query or "!!!" (error suffixes)
gai ace '"feature" AND "Drafted"'  # Filter by feature and status
gai ace -m big                     # Override model size (big/little)
gai ace -r 0                       # Disable auto-refresh
gai ace -r 30                      # Refresh every 30 seconds
```

**Options:**
- `-m, --model-size {big,little}`: Override model size for all AI operations
- `-r, --refresh-interval N`: Auto-refresh interval in seconds (default: 10, 0 to disable)

### gai axe

Schedule-based daemon for continuous ChangeSpec status updates.

```bash
gai axe                            # Start daemon with defaults
gai axe --full-check-interval 600  # Full check every 10 minutes
gai axe --hook-interval 5          # Check hooks every 5 seconds
gai axe -r 10                      # Allow 10 concurrent runners
gai axe -q '!!!'                   # Only monitor CLs with errors
gai axe --zombie-timeout 3600      # Mark processes as zombie after 1 hour
```

**Options:**
- `--full-check-interval N`: Full check interval in seconds (default: 300 = 5 minutes)
- `--hook-interval N`: Hook check interval in seconds (default: 1)
- `-r, --max-runners N`: Maximum concurrent runners (default: 5)
- `-q, --query QUERY`: Filter which ChangeSpecs to monitor
- `--zombie-timeout N`: Timeout for zombie detection in seconds (default: 7200 = 2 hours)

### gai commit

Create a Mercurial commit with formatted CL description and metadata.

```bash
gai commit my_feature              # Open vim to write commit message
gai commit my_feature message.txt  # Use file for commit message
gai commit my_feature -m "Message" # Direct message
gai commit my_feature -b 12345     # Associate with bug (BUG= tag)
gai commit my_feature -B 12345     # Bug is fixed by this CL (FIXED= tag)
gai commit my_feature -n "Note"    # Custom initial HISTORY note
gai commit my_feature -p project   # Override project name
gai commit my_feature --chat /path/chat.txt  # Associate with chat file
gai commit my_feature --timestamp 250125_103045  # Shared timestamp for synced files
gai commit my_feature --end-timestamp 250125_110000  # End timestamp for duration
```

### gai amend

Amend the current commit with HISTORY tracking.

```bash
gai amend "Fixed typo"             # Amend with note
gai amend -p                       # Create proposed HISTORY entry
gai amend -a 2a                    # Accept proposal entry 2a
gai amend -a '2b(Add field)'       # Accept with custom message
gai amend --chat /path/to/chat     # Associate with chat file
gai amend --cl my_feature -a 2a    # Accept on specific CL (not current branch)
gai amend --target-dir /path/dir   # Run commands in specific directory
gai amend --timestamp 250125_103045  # Shared timestamp for synced files
```

### gai restore

Restore a reverted ChangeSpec.

```bash
gai restore                        # Interactive selection
gai restore my_feature__2          # Restore specific reverted CL
gai restore -l                     # List all reverted ChangeSpecs
```

### gai revert

Revert a ChangeSpec by pruning its CL and archiving the diff.

```bash
gai revert my_feature              # Revert the specified CL
```

### gai search

Search for ChangeSpecs matching a query.

```bash
gai search '!!!'                   # Search for CLs with errors
gai search 'status:Drafted'        # Search by status
gai search 'myproject' -f plain    # Plain text output
gai search '@@@' -f rich           # Rich formatted output (default)
```

### gai xprompt

Expand gai references (snippets, file refs) in a prompt.

```bash
gai xprompt "Use @snippet:foo"     # Expand snippet reference
echo "prompt" | gai xprompt        # Read from stdin
```

### gai run

Execute workflows or arbitrary queries.

```bash
gai run crs                        # Address Critique comments
gai run fix-hook output.log "cmd"  # Fix failing hook
gai run mentor code:comments       # Run mentor agent
gai run split my_feature           # Split CL into multiple CLs
gai run summarize file.py "usage"  # Summarize a file
gai run "Your question here"       # Execute query directly
gai run                            # Open editor to write prompt
gai run .                          # Pick from prompt history
gai run -r                         # Resume last conversation
gai run -r history_file            # Resume specific conversation
gai run -l                         # List chat history files
gai run -a "Accept msg" "prompt"   # Auto-accept with custom message
gai run -c my_cl "Commit msg" "prompt"  # Override CL name and commit message
```

## Ace TUI Reference

### Tab Layout

The Ace TUI has three tabs:

1. **ChangeSpecs (CLs)**: Main view for managing change lists
2. **Agents**: View running and completed AI agents
3. **Axe**: Monitor the axe daemon status and output

### Keyboard Shortcuts

#### CLs Tab

| Section | Key | Action |
|---------|-----|--------|
| **Navigation** | `j` / `k` | Move to next / previous CL |
| | `< / > / ~` | Navigate to ancestor / child / sibling |
| | `Ctrl+O / K` | Jump back / forward in history |
| | `Ctrl+D / U` | Scroll detail panel down / up |
| **CL Actions** | `a` | Accept proposal |
| | `b` | Rebase CL onto parent |
| | `C / c1-c9` | Checkout CL (workspace 1-9) |
| | `d` | Show diff |
| | `e` | Edit spec file |
| | `h` | Edit hooks |
| | `H` | Add hooks from failed targets |
| | `M` | Mail CL |
| | `m` | Mark/unmark current CL |
| | `n` | Rename CL (non-Submitted/Reverted) |
| | `R` | Rewind to prev commit (non-Submitted/Reverted) |
| | `s` | Change status |
| | `T / t1-t9` | Checkout + tmux (workspace 1-9) |
| | `u` | Clear all marks |
| | `v` | View files |
| | `w` | Reword CL description |
| | `Y` | Sync workspace |
| **Fold Mode** | `z c` | Toggle commits section |
| | `z h` | Toggle hooks section |
| | `z m` | Toggle mentors section |
| | `z z` | Toggle all sections |
| **Workflows & Agents** | `r` | Run workflow |
| | `@` | Run agent on marked CLs (or current) |
| | `!` | Run background command |
| | `<space>` | Run agent from current CL |
| **Queries** | `/` | Edit search query |
| | `0-9` | Load saved query |
| | `^` | Previous query |
| | `_` | Next query |
| **Copy Mode (%)** | `%%` | Copy ChangeSpec |
| | `%!` | Copy ChangeSpec + snapshot |
| | `%b` | Copy bug number |
| | `%c` | Copy CL number |
| | `%n` | Copy CL name |
| | `%p` | Copy project spec file |
| | `%s` | Copy gai ace snapshot |
| **Axe Control** | `X` | Start / stop axe (or select process) |
| | `Q` | Stop axe and quit |
| **General** | `Tab / Shift+Tab` | Switch tabs |
| | `.` | Show/hide reverted CLs |
| | `y` | Refresh |
| | `q` | Quit |
| | `?` | Show help |

#### Agents Tab

| Section | Key | Action |
|---------|-----|--------|
| **Navigation** | `j` / `k` | Move to next / previous agent |
| | `Ctrl+D / U` | Scroll diff panel down / up |
| | `Ctrl+F / B` | Scroll prompt panel down / up |
| **Agent Actions** | `@` | Run custom agent |
| | `!` | Run background command |
| | `r` | Revive chat as agent |
| | `x` | Kill / dismiss agent |
| | `e` | Edit chat in editor |
| | `l` | Toggle diff/prompt layout |
| **Axe Control** | `X` | Start / stop axe (or select process) |
| | `Q` | Stop axe and quit |
| **General** | `Tab / Shift+Tab` | Switch tabs |
| | `.` | Show/hide non-run agents |
| | `%` | Copy chat to clipboard |
| | `y` | Refresh |
| | `q` | Quit |
| | `?` | Show help |

#### Axe Tab

| Section | Key | Action |
|---------|-----|--------|
| **Navigation** | `j` / `k` | Move to next / previous command |
| | `g` | Scroll to top |
| | `G` | Scroll to bottom |
| **Background Commands** | `@` | Run agent |
| | `!` | Run background command |
| | `X` | Kill current command (or toggle axe) |
| **Axe Control** | `x` | Clear output |
| | `X` | Start / stop axe daemon |
| | `Q` | Stop axe and quit |
| **General** | `Tab / Shift+Tab` | Switch tabs |
| | `%` | Copy output to clipboard |
| | `y` | Refresh |
| | `q` | Quit |
| | `?` | Show help |

### Status Indicators

ChangeSpecs display status indicators in the format `[!@$D]`:

| Indicator | Meaning | Color |
|-----------|---------|-------|
| `!` | Has error suffix | Red |
| `@` | Running agent | Orange |
| `$` | Running process | Yellow |
| `D` | Drafted status | Cyan |
| `*` | Ready to mail | Cyan |
| `~` | In progress | Gray |

## Axe Daemon Reference

The axe daemon provides continuous background monitoring of ChangeSpecs.

### What It Does

- **Hook Management**: Automatically runs and monitors hook commands
- **CL Status Checks**: Monitors CL submission status
- **Comment Monitoring**: Checks for new reviewer/author comments
- **Mentor Execution**: Runs configured mentor agents
- **Workflow Management**: Manages CRS and fix-hook workflows
- **Zombie Detection**: Identifies stuck processes

### State Files

All state files are stored in `~/.axe_state/`:

- `pid.txt`: Current daemon PID
- `status.json`: Current daemon status
- `metrics.json`: Runtime metrics
- `errors.json`: Error log
- `cycle_result.json`: Last cycle results
- `logs/output.log`: Daemon output log

### Controlling from Ace TUI

- `X`: Toggle axe daemon on/off
- `Q`: Stop axe and quit ace
- View Axe tab for live output and metrics

## ChangeSpec Format

A ChangeSpec defines the metadata for a change list. See [docs/change_spec.md](docs/change_spec.md) for the full specification.

### Basic Fields

```
NAME: project_feature_name
DESCRIPTION:
  Brief one-line title

  Detailed multi-line description of what the CL does
  and why it's needed.
PARENT: project_parent_cl  # Optional, for dependent CLs
CL: http://cl/12345        # Set after CL creation
STATUS: Drafted
BUG: b/12345               # Associated bug number
TEST TARGETS: //path/to:test
KICKSTART:                 # Optional kickstart prompt for AI workflows
  Initial context or instructions for AI agents
```

### Status Values

- `Blocked`: Has unsubmitted PARENT
- `Unstarted`: Ready to start
- `In Progress`: Work ongoing
- `Failed to Create CL`: CL creation failed
- `TDD CL Created`: Test-driven CL created
- `Fixing Tests`: Tests failing
- `Failed to Fix Tests`: Cannot fix tests
- `Drafted`: Ready for review
- `Mailed`: Sent for review
- `Submitted`: Merged

### Sections

- **COMMITS**: History of commits with notes and diffs
- **HOOKS**: Commands to run for validation
- **MENTORS**: AI mentor status entries
- **COMMENTS**: Reviewer feedback entries

## Query Language Reference

The query language supports boolean logic, property filters, and convenient shorthands.

### Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `AND` | `"foo" AND "bar"` | Both conditions must match |
| `OR` | `"foo" OR "bar"` | Either condition matches |
| `NOT` | `NOT "foo"` | Negates condition |

### String Matching

Quoted strings match against all searchable text:

```bash
'"feature"'              # Match "feature" anywhere
'"my_project"'           # Match project or CL name
'"Drafted"'              # Match status
```

### Property Filters

| Filter | Example | Description |
|--------|---------|-------------|
| `status:` | `status:Drafted` | Match exact status |
| `project:` | `project:myproj` | Match project name |
| `name:` | `name:my_feature` | Match exact CL name |
| `ancestor:` | `ancestor:parent_cl` | Match CL or any parent in chain |
| `sibling:` | `sibling:related_cl` | Match CLs in same "family" |

### Special Marker Shorthands

| Shorthand | Meaning | Matches |
|-----------|---------|---------|
| `!!!` | Error suffix | CLs with any `(!:` error suffix |
| `@@@` | Running agent | CLs with `(@:` running agent marker |
| `$$$` | Running process | CLs with `($:` running process marker |
| `!` | (standalone) | Same as `!!!` |
| `@` | (standalone) | Same as `@@@` |
| `$` | (standalone) | Same as `$$$` |
| `*` | Any special | `(!!! OR @@@ OR $$$)` |

### Negation Shorthands

| Shorthand | Expands To | Description |
|-----------|------------|-------------|
| `!!` | `NOT !!!` | No error suffix |
| `!@` | `NOT @@@` | No running agents |
| `!$` | `NOT $$$` | No running processes |

### Status Shorthands

| Shorthand | Expands To |
|-----------|------------|
| `%d` | `status:DRAFTED` |
| `%m` | `status:MAILED` |
| `%r` | `status:REVERTED` |
| `%s` | `status:SUBMITTED` |
| `%w` | `status:WIP` |

### Property Filter Shorthands

| Shorthand | Expands To | Example |
|-----------|------------|---------|
| `+name` | `project:name` | `+myproject` |
| `^name` | `ancestor:name` | `^parent_cl` |
| `~name` | `sibling:name` | `~related_cl` |
| `&name` | `name:name` | `&my_feature` |

### Examples

```bash
# CLs with errors
'!!!'
'!'                      # Shorthand for !!!

# Running agents
'@@@'
'@'                      # Shorthand for @@@

# Any CL with errors, running agents, or processes
'*'

# CLs without errors
'!!'

# Drafted CLs in project "foo"
'status:Drafted AND project:foo'
'%d +foo'                # Same, using shorthands

# Feature CLs not yet mailed
'"feature" AND NOT status:Mailed'

# All descendants of a parent CL
'ancestor:my_parent_cl'
'^my_parent_cl'          # Same, using shorthand

# Complex filter
'(status:Drafted OR status:Mailed) AND project:myproj AND NOT !!!'
'(%d OR %m) +myproj !!'  # Same, using shorthands
```

## Workflows Reference

### gai run crs

Address Critique change request comments on a CL.

```bash
gai run crs                        # Run on current branch
gai run crs -D /path/to/context    # Add context files directory
```

Uses AI to analyze and address reviewer comments automatically.

### gai run fix-hook

Fix a failing hook command using AI assistance.

```bash
gai run fix-hook output.log "make lint"
```

- `hook_output_file`: Path to file with hook command output
- `hook_command`: The failing command string

### gai run mentor

Run a mentor agent to enforce coding standards.

```bash
gai run mentor code:comments       # Run comments mentor
gai run mentor style:formatting    # Run formatting mentor
gai run mentor --cl my_feature     # Target specific CL
```

Format: `profile:mentor` (e.g., `code:comments`)

### gai run split

Split a CL into multiple smaller CLs based on a SplitSpec.

```bash
gai run split                      # Split current branch
gai run split my_feature           # Split specific CL
gai run split -s                   # Open editor to create spec
gai run split -s spec.yaml         # Use existing spec file
gai run split -y                   # Auto-approve all prompts
```

### gai run summarize

Summarize a file in 20 words or less.

```bash
gai run summarize file.py "a commit message"
gai run summarize README.md "documentation"
```

## Configuration Reference

Configuration is stored in `~/.config/gai/gai.yml`.

### Snippets

Custom prompt templates that can be referenced with `@snippet:name`:

```yaml
snippets:
  guidelines: |
    Follow these coding guidelines:
    - Use type hints
    - Write docstrings
  review_prompt: |
    Review this code for:
    - Security issues
    - Performance problems
```

Usage in prompts:
```
Please @snippet:guidelines when reviewing this code.
```

### Mentor Profiles

Configure mentor agents with matching criteria:

```yaml
mentor_profiles:
  - profile_name: code
    file_globs:
      - "*.py"
      - "*.js"
    mentors:
      - mentor_name: comments
        prompt: |
          Review this diff for adequate code comments.
          Suggest improvements where documentation is lacking.
      - mentor_name: typing
        prompt: |
          Check that all functions have proper type annotations.
        run_on_wip: true  # Run even on WIP status

  - profile_name: docs
    file_globs:
      - "*.md"
      - "*.rst"
    diff_regexes:
      - "^\\+.*TODO"
    mentors:
      - mentor_name: todo_check
        prompt: Check for unresolved TODOs in documentation.
```

**Matching Criteria** (at least one required):
- `file_globs`: Glob patterns for changed file paths
- `diff_regexes`: Regex patterns to match diff content
- `amend_note_regexes`: Regex patterns to match commit notes

**Mentor Options:**
- `mentor_name`: Unique identifier for the mentor
- `prompt`: The AI prompt for this mentor
- `run_on_wip`: Run even when status is WIP (default: false)

## Architecture Overview

### Module Structure

```
src/
├── main/              # CLI entry points and argument parsing
│   ├── entry.py       # Main entry point
│   ├── parser.py      # Argument parser
│   └── query_handler/ # Query and workflow handlers
├── ace/               # TUI and ChangeSpec management
│   ├── tui/           # Textual TUI application
│   │   ├── app.py     # Main TUI app
│   │   ├── modals/    # Modal dialogs
│   │   └── widgets/   # UI widgets
│   ├── changespec/    # ChangeSpec parsing and manipulation
│   ├── query/         # Query language parser and evaluator
│   ├── hooks/         # Hook command management
│   ├── comments/      # Comment entry handling
│   └── scheduler/     # Background task scheduling
├── axe/               # Daemon implementation
│   ├── core.py        # Main scheduler
│   ├── state.py       # State file management
│   └── runner_pool.py # Concurrent runner management
├── gemini_wrapper/    # AI/Gemini integration
│   ├── snippet_processor.py
│   └── file_references.py
├── commit_workflow/   # Commit creation logic
├── amend_workflow.py  # Amend handling
├── fix_hook_workflow.py
├── summarize_workflow.py
├── mentor_config.py   # Mentor configuration
└── snippet_config.py  # Snippet configuration
```

### Design Patterns

- **Workflow-based**: Each major operation is a self-contained workflow
- **LangGraph**: AI workflows use LangGraph for agent orchestration
- **Textual TUI**: Rich terminal UI using the Textual framework
- **Schedule-based daemon**: axe uses the `schedule` library for timed tasks
- **Query DSL**: Custom query language with parser and evaluator

## Data Storage Reference

### Project Files

```
~/.gai/projects/<project>/
├── <project>.gp              # Main ProjectSpec file
├── context/                  # Context files for AI
└── artifacts/<workflow>/<timestamp>/
    ├── chat.txt              # Conversation log
    ├── diff.patch            # Generated diff
    └── ...
```

### Chat History

```
~/.gai/chats/
├── <timestamp>_<workflow>.txt
└── ...
```

### Saved Queries

```
~/.gai/
├── saved_queries.json        # Slots 0-9
└── last_query.txt            # Most recent query
```

### Axe State

```
~/.axe_state/
├── pid.txt                   # Daemon PID
├── status.json               # Current status
├── metrics.json              # Runtime metrics
├── errors.json               # Error log
├── cycle_result.json         # Last cycle result
└── logs/
    └── output.log            # Daemon output
```

## Suffix System Reference

Suffixes indicate the state of COMMITS, HOOKS, COMMENTS, and MENTORS entries.

### Suffix Types

| Suffix | Type | Meaning | Color |
|--------|------|---------|-------|
| `(!: msg)` | error | Error occurred | White on red |
| `(@: msg)` | running_agent | AI agent running | White on orange |
| `(@)` | running_agent | Agent running (no message) | White on orange |
| `($: PID)` | running_process | Process running with PID | Brown on gold |
| `(?$: PID)` | pending_dead_process | Process may be dead | Gold on gray |
| `(~$: PID)` | killed_process | Process was killed | Olive on gray |
| `(~@: msg)` | killed_agent | Agent was killed | Orange on gray |
| `(~!: msg)` | rejected_proposal | Proposal rejected | Light red on gray |
| `(%: msg)` | summarize_complete | Summarization done | White on teal |
| `(entry_ref)` | entry_ref | Reference to entry | Bold pink |

### Query Shorthands

| Pattern | Matches |
|---------|---------|
| `!!!` or `!` | Any entry with `(!:` error suffix |
| `@@@` or `@` | Any entry with `(@` running agent marker |
| `$$$` or `$` | Any entry with `($:` running process marker |
| `*` | Any entry with error, running agent, or running process |
| `!!` | No error suffix (`NOT !!!`) |
| `!@` | No running agents (`NOT @@@`) |
| `!$` | No running processes (`NOT $$$`) |

### Status Suffix Styling

The status indicator `[!@$D]` in the CL list shows:

- **!** (red): Has error suffixes
- **@** (orange): Has running agents
- **$** (yellow): Has running processes
- **D** (cyan): Drafted status
- **\*** (cyan): Ready to mail
