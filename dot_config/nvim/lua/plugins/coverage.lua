--- Displays test coverage data in the sign column.

return {
	-- PLUGIN: http://github.com/andythigpen/nvim-coverage
	{
		"andythigpen/nvim-coverage",
		config = function()
			require("coverage").setup({ auto_reload = true })
		end,
		dependencies = "nvim-lua/plenary.nvim",
	},
}
