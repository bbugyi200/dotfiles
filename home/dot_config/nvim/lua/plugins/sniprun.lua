--- Run code snippets in NeoVim using the best available tool.

return {
	-- PLUGIN: http://github.com/michaelb/sniprun
	{
		"michaelb/sniprun",
		build = "sh ./install.sh 1",
		dependencies = { "rcarriga/nvim-notify" },
		cmd = "SnipRun",
		keys = {
			-- KEYMAP: <leader>r
			--
			-- P2: Migrate <leader>r function() logic to 'zorg' Generic?!
			{
				"<leader>r",
				function()
					local line = vim.api.nvim_get_current_line()
					if line:find("`") ~= nil and line:find("```") == nil then
						vim.cmd('normal "ryi`')
						-- P2: Add support for running inline code snippets created for ANY language!
						local code_string = vim.fn.getreg("r")
						local run_string = require("sniprun.api").run_string
						local filetype
						if code_string:find("^:") ~= nil then
							filetype = "vim"
						else
							filetype = "bash"
						end
						run_string(code_string, filetype)
					else
						vim.cmd("SnipRun")
					end
				end,
				desc = "Run inline / a single line of / a single block of code using SnipRun.",
			},
			-- KEYMAP: <leader>r (visual)
			{ "<leader>r", "<Plug>SnipRun", mode = "v", desc = "Run the visually selected code using SnipRun." },
			-- KEYMAP: <leader><leader>r
			{
				"<leader><leader>r",
				"<Plug>SnipRunOperator",
				desc = "Execute lines of code specified by an operator motion.",
			},
		},
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
	},
}
