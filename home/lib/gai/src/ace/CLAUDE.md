# Ace Subcommand Guidelines

## ChangeSpec Suffix Syntax Highlighting

**CRITICAL**: When updating styling for ChangeSpec suffix types (e.g., `killed_process`, `running_agent`, `error`), you MUST update ALL of these files:

1. `home/dot_config/nvim/syntax/gaiproject.vim` - Vim syntax highlighting (2 places: COMMITS and HOOKS sections)
2. `home/lib/gai/ace/display.py` - CLI Rich styling (3 places: commits, hooks, comments)
3. `home/lib/gai/ace/query/highlighting.py` - Query token styles in `QUERY_TOKEN_STYLES` dict
4. `home/lib/gai/ace/tui/widgets/changespec_detail.py` - TUI widget Rich styling (3 places: commits, hooks, comments)

## Help Popup Maintenance

**CRITICAL**: Whenever you modify a `gai ace` option (add, remove, or change behavior), you MUST update the `?` (help) popup content to keep the documentation in sync with the actual functionality.

## Help Modal Box Formatting

**CRITICAL**: The help modal boxes must maintain consistent 57-character width. When modifying `help_modal.py`:

1. All box sections use `_BOX_WIDTH = 57` and `_CONTENT_WIDTH = 50`
2. Keybinding descriptions: max 32 chars (truncate with "..." if longer)
3. Saved query display: max 36 chars when active indicator shown, 45 chars otherwise
