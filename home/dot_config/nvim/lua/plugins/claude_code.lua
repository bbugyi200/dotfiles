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

			-- KEYMAP: <localleader>A
			vim.keymap.set("n", "<localleader>A", "<cmd>ClaudeCode<cr>", { desc = "Toggle Claude Code terminal." })

			-- KEYMAP: <localleader>aC
			vim.keymap.set(
				"n",
				"<localleader>aC",
				"<cmd>ClaudeCodeContinue<cr>",
				{ desc = "Continue the most recent Claude Code conversation." }
			)

			-- KEYMAP: <localleader>aR
			vim.keymap.set(
				"n",
				"<localleader>aR",
				"<cmd>ClaudeCodeResume<cr>",
				{ desc = "Resume a previous Claude Code conversation from history." }
			)

			-- KEYMAP: <localleader>aV
			vim.keymap.set(
				"n",
				"<localleader>aV",
				"<cmd>ClaudeCodeVerbose<cr>",
				{ desc = "Enable verbose output for Claude Code." }
			)

			-- KEYMAP: <localleader>A (terminal mode)
			vim.keymap.set(
				"t",
				"<localleader>A",
				"<cmd>ClaudeCode<cr>",
				{ desc = "Toggle Claude Code terminal from terminal mode." }
			)
		end,
	},
}
