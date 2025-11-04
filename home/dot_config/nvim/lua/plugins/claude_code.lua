-- PLUGIN: https://github.com/greggh/claude-code.nvim
local bb = require("bb_utils")

-- Only load this plugin on personal (non-Google) machines
if bb.is_goog_machine() then
	return {}
end

return {
	{
		"greggh/claude-code.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim", -- Required for git operations
		},
		config = function()
			require("claude-code").setup({
				command = "claude --dangerously-skip-permissions",
				window = {
					position = "float",
					float = {
						width = "90%",
						height = "90%",
						row = "center",
						col = "center",
						border = "rounded",
					},
				},
			})
		end,
		init = function()
			-- KEYMAP GROUP: <localleader>a
			vim.keymap.set("n", "<localleader>a", "<nop>", { desc = "claude-code.nvim" })

			-- KEYMAP: <localleader>ac
			vim.keymap.set(
				"n",
				"<localleader>ac",
				"<cmd>ClaudeCodeContinue<cr>",
				{ desc = "Continue the most recent Claude Code conversation." }
			)

			-- KEYMAP: <localleader>ai
			vim.keymap.set("n", "<localleader>ai", "<cmd>ClaudeCode<cr>", { desc = "Toggle Claude Code terminal." })

			-- KEYMAP: <localleader>a (terminal mode)
			vim.keymap.set(
				"t",
				"<localleader>a",
				"<cmd>ClaudeCode<cr>",
				{ desc = "Toggle Claude Code terminal from terminal mode." }
			)

			-- KEYMAP: <localleader>ar
			vim.keymap.set(
				"n",
				"<localleader>ar",
				"<cmd>ClaudeCodeResume<cr>",
				{ desc = "Resume a previous Claude Code conversation from history." }
			)

			-- KEYMAP: <localleader>av
			vim.keymap.set(
				"n",
				"<localleader>av",
				"<cmd>ClaudeCodeVerbose<cr>",
				{ desc = "Enable verbose output for Claude Code." }
			)
		end,
	},
}
