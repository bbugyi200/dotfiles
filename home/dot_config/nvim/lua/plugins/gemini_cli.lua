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
			-- Build args from environment variable
			local args = { "--yolo" }

			-- Parse GAI_BIG_GEMINI_ARGS environment variable
			local extra_args_env = os.getenv("GAI_BIG_GEMINI_ARGS")
			if extra_args_env then
				-- Split on whitespace and add each arg
				for arg in extra_args_env:gmatch("%S+") do
					table.insert(args, arg)
				end
			end

			require("gemini_cli").setup({
				gemini_cmd = "/google/bin/releases/gemini-cli/tools/gemini",
				args = args,
				win = {
					position = "float",
					width = 0.9,
					height = 0.9,
					border = "rounded",
				},
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
