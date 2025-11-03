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
			-- KEYMAP GROUP: <localleader>a
			vim.keymap.set("n", "<localleader>a", "<nop>", { desc = "gemini-cli.nvim" })

			-- KEYMAP: <localleader>A
			vim.keymap.set("n", "<localleader>A", "<cmd>Gemini toggle<cr>", { desc = "Toggle Gemini CLI terminal." })

			-- KEYMAP: <localleader>aa
			vim.keymap.set({ "n", "v" }, "<localleader>aa", "<cmd>Gemini ask<cr>", { desc = "Ask Gemini a question." })

			-- KEYMAP: <localleader>af
			vim.keymap.set(
				"n",
				"<localleader>af",
				"<cmd>Gemini add_file<cr>",
				{ desc = "Add current file to Gemini session." }
			)

			-- KEYMAP: <localleader>ah
			vim.keymap.set(
				"n",
				"<localleader>ah",
				"<cmd>Gemini health<cr>",
				{ desc = "Check Gemini CLI health status." }
			)

			-- KEYMAP: <localleader>A (terminal mode)
			vim.keymap.set(
				"t",
				"<localleader>A",
				"<cmd>Gemini toggle<cr>",
				{ desc = "Toggle Gemini CLI terminal from terminal mode." }
			)
		end,
	},
}
