--- An extensible framework for interacting with tests within NeoVim.

return {
	-- PLUGIN: http://github.com/nvim-neotest/neotest
	{
		"nvim-neotest/neotest",
		dependencies = {
			"nvim-neotest/nvim-nio",
			"nvim-lua/plenary.nvim",
			"antoinemadec/FixCursorHold.nvim",
			"nvim-treesitter/nvim-treesitter",
			-- ADAPTERS!
			"nvim-neotest/neotest-python",
		},
		config = function()
			---@diagnostic disable-next-line: missing-fields
			require("neotest").setup({
				adapters = {
					require("neotest-python")({ dap = { justMyCode = false } }),
				},
			})
		end,
		init = function()
			-- KEYMAP(N): <leader>nto
			vim.keymap.set(
				"n",
				"<leader>nto",
				"<cmd>Neotest output-panel<cr>",
				{ desc = "Run ':Neotest output-panel' command." }
			)

			-- KEYMAP(N): <leader>ntr
			vim.keymap.set("n", "<leader>ntr", "<cmd>Neotest run<cr>", {
				desc = "Run ':Neotest run' command.",
			})

			-- KEYMAP(N): <leader>nts
			vim.keymap.set("n", "<leader>nts", "<cmd>Neotest summary<cr>", {
				desc = "Run ':Neotest summary' command.",
			})
		end,
	},
}
