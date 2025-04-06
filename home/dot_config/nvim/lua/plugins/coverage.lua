--- Displays test coverage data in the sign column.

local is_goog_machine = require("util.is_goog_machine")

if is_goog_machine() then
	-- Conflicts with http://go/coverage-google plugin!
	return {}
else
	return {
		-- PLUGIN: http://github.com/andythigpen/nvim-coverage
		{
			"andythigpen/nvim-coverage",
			opts = { auto_reload = true },
			dependencies = "nvim-lua/plenary.nvim",
			init = function()
				-- KEYMAP: <leader>ncc
				vim.keymap.set("n", "<leader>ncc", "<cmd>Coverage<cr>", { desc = "Run :Coverge command." })

				-- KEYMAP: <leader>ncs
				vim.keymap.set(
					"n",
					"<leader>ncs",
					"<cmd>CoverageSummary<cr>",
					{ desc = "Run :CoverageSummary command." }
				)
			end,
		},
	}
end
