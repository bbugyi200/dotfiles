--- Displays test coverage data in the sign column.

return {
	-- PLUGIN: http://github.com/andythigpen/nvim-coverage
	{
		"andythigpen/nvim-coverage",
		config = function()
			require("coverage").setup({ auto_reload = true })
		end,
		dependencies = "nvim-lua/plenary.nvim",
		init = function()
			-- KEYMAP(N): <leader>ncc
			vim.keymap.set("n", "<leader>ncc", "<cmd>Coverage<cr>", { desc = "Run :Coverge command." })

			-- KEYMAP(N): <leader>ncs
			vim.keymap.set("n", "<leader>ncs", "<cmd>CoverageSummary<cr>", { desc = "Run :CoverageSummary command." })
		end,
	},
}
