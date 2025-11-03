# Neovim Configuration Style Guide

## Plugin Organization

### Single-File Plugins (Preferred)

Most plugins should be contained in **single files** in the `/lua/plugins/` directory. Each plugin file should:

1. Start with module documentation comments
2. Include any helper functions (preferably private)
3. Return a lazy.nvim plugin spec (table)

**Example Structure:**
```lua
-- PLUGIN: http://github.com/author/plugin-name
return {
	{
		"author/plugin-name",
		dependencies = { ... },
		opts = { ... },
		init = function()
			-- Configuration here

			-- Keymaps (if any)
			-- KEYMAP: <leader>x
			vim.keymap.set("n", "<leader>x", ..., { desc = "Description" })
		end,
	},
}
```

### Multi-File Plugins (For Complex Ecosystems)

Use subdirectories only for complex plugin ecosystems (e.g., DAP, CodeCompanion):

```
/lua/plugins/
├── pluginname/
│   ├── init.lua           (main plugin spec)
│   ├── config.lua         (shared configuration)
│   └── helpers.lua        (helper functions)
```

## Keymap Conventions

### Leader Keys

- **Leader**: `,` (comma)
- **Local Leader**: `\` (backslash)

### Documentation Format

**CRITICAL**: Every keymap MUST have a preceding comment documenting the key binding.

#### Individual Keymaps

Use `-- KEYMAP:` followed by the key binding:

```lua
-- KEYMAP: <leader>s
vim.keymap.set(
	{ "n", "i" },
	"<leader>s",
	"<cmd>update<cr>",
	{ desc = "Save the current file if it has been modified." }
)
```

#### Keymap Groups

For multi-part keymaps (e.g., `<leader>q`, `<leader>qa`, `<leader>qf`), use `-- KEYMAP GROUP:`:

```lua
-- KEYMAP GROUP: <leader>q
vim.keymap.set("n", "<leader>q", "<nop>", { desc = "Quickfix" })

-- KEYMAP: <leader>qa
vim.keymap.set("n", "<leader>qa", function()
	-- Add all buffers to quickfix
end, { desc = "Add all open buffers to the quickfix window." })

-- KEYMAP: <leader>qf
vim.keymap.set("n", "<leader>qf", "<cmd>copen<cr>", { desc = "Open quickfix window." })
```

### Requirements

1. **Always include `desc` field**: Used by which-key plugin for documentation
2. **Use `<nop>` for groups**: Creates prefix groups without executing commands
3. **Document before defining**: Place `-- KEYMAP:` comment immediately before the `vim.keymap.set()` call

### Examples

#### Basic Keymap
```lua
-- KEYMAP: <leader>e
vim.keymap.set(
	{ "n", "i" },
	"<leader>e",
	"<cmd>x!<cr>",
	{ desc = "Save current file and exit vim / close current buffer." }
)
```

#### Function-based Keymap
```lua
-- KEYMAP: <leader>qa
vim.keymap.set("n", "<leader>qa", function()
	local buffers = vim.api.nvim_list_bufs()
	-- ... implementation
end, { desc = "Add all open buffers to the quickfix window." })
```

#### Plugin-specific Keymaps (Local Leader)

AI tools and plugin-specific features use `<localleader>` (backslash):

```lua
-- KEYMAP GROUP: <localleader>a
vim.keymap.set("n", "<localleader>a", "<nop>", { desc = "claude-code.nvim" })

-- KEYMAP: <localleader>ai
vim.keymap.set("n", "<localleader>ai", "<cmd>ClaudeCode<cr>", { desc = "Toggle Claude Code terminal." })

-- KEYMAP: <localleader>aC
vim.keymap.set("n", "<localleader>aC", "<cmd>ClaudeCodeContinue<cr>", { desc = "Continue the most recent Claude Code conversation." })
```
