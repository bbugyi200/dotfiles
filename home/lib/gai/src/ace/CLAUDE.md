# Ace Subcommand Guidelines

## ChangeSpec Suffix Syntax Highlighting

**CRITICAL**: When updating styling for ChangeSpec suffix types (e.g., `killed_process`, `running_agent`, `error`), you MUST update ALL of these files:

1. `home/dot_config/nvim/syntax/gaiproject.vim` - Vim syntax highlighting (2 places: COMMITS and HOOKS sections)
2. `home/lib/gai/ace/display.py` - CLI Rich styling (3 places: commits, hooks, comments)
3. `home/lib/gai/ace/query/highlighting.py` - Query token styles in `QUERY_TOKEN_STYLES` dict
4. `home/lib/gai/ace/tui/widgets/changespec_detail.py` - TUI widget Rich styling (3 places: commits, hooks, comments)

## Help Popup Maintenance

**CRITICAL**: Whenever you modify a `gai ace` option (add, remove, or change behavior), you MUST update the `?` (help) popup content to keep the documentation in sync with the actual functionality.
