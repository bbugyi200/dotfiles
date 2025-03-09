--- Displays test coverage data in the sign column.

return {
	-- PLUGIN: http://github.com/andythigpen/nvim-coverage
	{
		"andythigpen/nvim-coverage",
		opts = {},
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
