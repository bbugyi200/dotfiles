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
			-- KEYMAP GROUP: <localleader>c
			vim.keymap.set("n", "<localleader>c", "<nop>", { desc = "claude-code.nvim" })

			-- KEYMAP: <localleader>c
			vim.keymap.set("n", "<localleader>c", "<cmd>ClaudeCode<cr>", { desc = "Toggle Claude Code terminal." })

			-- KEYMAP: <localleader>cC
			vim.keymap.set(
				"n",
				"<localleader>cC",
				"<cmd>ClaudeCodeContinue<cr>",
				{ desc = "Continue the most recent Claude Code conversation." }
			)

			-- KEYMAP: <localleader>cR
			vim.keymap.set(
				"n",
				"<localleader>cR",
				"<cmd>ClaudeCodeResume<cr>",
				{ desc = "Resume a previous Claude Code conversation from history." }
			)

			-- KEYMAP: <localleader>cV
			vim.keymap.set(
				"n",
				"<localleader>cV",
				"<cmd>ClaudeCodeVerbose<cr>",
				{ desc = "Enable verbose output for Claude Code." }
			)

			-- KEYMAP: <localleader>c (terminal mode)
			vim.keymap.set(
				"t",
				"<localleader>c",
				"<cmd>ClaudeCode<cr>",
				{ desc = "Toggle Claude Code terminal from terminal mode." }
			)
		end,
	},
}
