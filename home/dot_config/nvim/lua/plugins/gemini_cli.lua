-- PLUGIN: https://github.com/marcinjahn/gemini-cli.nvim
local bb = require("bb_utils")

-- Only load this plugin on Google/work machines
if not bb.is_goog_machine() then
	return {}
end

return {
	{
		"marcinjahn/gemini-cli.nvim",
		dependencies = {
			"folke/snacks.nvim", -- Required for UI components
		},
		config = function()
			require("gemini_cli").setup({
				args = { "big" },
			})
		end,
		init = function()
			-- KEYMAP GROUP: <localleader>g
			vim.keymap.set("n", "<localleader>g", "<nop>", { desc = "gemini-cli.nvim" })

			-- KEYMAP: <localleader>g
			vim.keymap.set("n", "<localleader>g", "<cmd>Gemini toggle<cr>", { desc = "Toggle Gemini CLI terminal." })

			-- KEYMAP: <localleader>ga
			vim.keymap.set({ "n", "v" }, "<localleader>ga", "<cmd>Gemini ask<cr>", { desc = "Ask Gemini a question." })

			-- KEYMAP: <localleader>gf
			vim.keymap.set(
				"n",
				"<localleader>gf",
				"<cmd>Gemini add_file<cr>",
				{ desc = "Add current file to Gemini session." }
			)

			-- KEYMAP: <localleader>gh
			vim.keymap.set(
				"n",
				"<localleader>gh",
				"<cmd>Gemini health<cr>",
				{ desc = "Check Gemini CLI health status." }
			)
		end,
	},
}
