--- Displays test coverage data in the sign column.

return {
	-- PLUGIN: http://github.com/andythigpen/nvim-coverage
	{
		"andythigpen/nvim-coverage",
		config = function()
			require("coverage").setup()
		end,
		dependencies = "nvim-lua/plenary.nvim",
		cmd = {
			"Coverage",
			"CoverageSummary",
			"CoverageLoad",
			"CoverageShow",
			"CoverageHide",
			"CoverageToggle",
			"CoverageClear",
		},
	},
}
