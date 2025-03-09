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
			"rcasia/neotest-bash",
			"nvim-neotest/neotest-python",
		},
		config = function()
			---@diagnostic disable-next-line: missing-fields
			require("neotest").setup({
				adapters = {
					require("neotest-bash"),
					require("neotest-python")({ dap = { justMyCode = false } }),
				},
			})
		end,
	},
}
