--- Run code snippets in NeoVim using the best available tool.

return {
	-- PLUGIN: http://github.com/michaelb/sniprun
	{
		"michaelb/sniprun",
		build = "sh ./install.sh",
		dependencies = { "rcarriga/nvim-notify" },
		opts = {
			interpreter_options = {
				Generic = {
					error_truncate = "long",
					VimConfig = {
						supported_filetypes = { "vim" },
						interpreter = "sniprun_nvim " .. vim.v.servername,
						boilerplate_pre = "vim.cmd([[",
						boilerplate_post = "]])",
					},
				},
				GFM_original = {
					use_on_filetypes = { "zorg" },
					default_filetype = "bash",
				},
			},
			display = { "NvimNotify" },
			display_options = {
				notification_timeout = 5, -- in seconds
				notification_render = "default", -- nvim-notify render style
			},
			selected_interpreters = { "Generic" },
		},
		init = function()
			-- KEYMAP(N): <leader>r
			vim.keymap.set("n", "<leader>r", function()
				local line = vim.api.nvim_get_current_line()
				if line:find("`") ~= nil and line:find("```") == nil then
					local sniprun = require("sniprun.api")
					vim.cmd('normal "ryi`')
					local code = vim.fn.getreg("r")
					-- P2: Add support for running inline code snippets created for ANY language!
					if code:find("^:") ~= nil then
						sniprun.run_string(code, "vim")
					else
						sniprun.run_string(code, "bash")
					end
				else
					vim.cmd("SnipRun")
				end
			end, { desc = "Run inline / a single line of / a single block of code using SnipRun." })
			-- KEYMAP(V): <leader>r
			vim.keymap.set(
				"v",
				"<leader>r",
				"<plug>SnipRun",
				{ desc = "Run the visually selected code using SnipRun." }
			)
			-- KEYMAP(N): <localleader>r
			vim.keymap.set(
				"n",
				"<localleader>r",
				"<plug>SnipRunOperator",
				{ desc = "Execute lines of code specified by an operator motion." }
			)
		end,
	},
}
