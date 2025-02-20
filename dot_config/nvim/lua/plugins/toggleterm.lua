--- A neovim lua plugin to help easily manage multiple terminal windows.

return {
	-- PLUGIN: http://github.com/akinsho/toggleterm.nvim
	{
		"akinsho/toggleterm.nvim",
		opts = {},
		init = function()
			local Terminal = require("toggleterm.terminal").Terminal
			local lazygit = Terminal:new({
				cmd = "lazygit",
				dir = "git_dir",
				direction = "float",
				float_opts = {
					border = "double",
				},
				-- function to run on opening the terminal
				on_open = function(term)
					vim.cmd("startinsert!")
					vim.api.nvim_buf_set_keymap(
						term.bufnr,
						"n",
						"q",
						"<cmd>close<CR>",
						{ noremap = true, silent = true }
					)
				end,
				-- function to run on closing the terminal
				on_close = function(_)
					vim.cmd("startinsert!")
				end,
			})

			function _LazygitToggle()
				lazygit:toggle()
			end

			-- KEYMAP(N): <leader>gl
			vim.keymap.set(
				"n",
				"<leader>gl",
				"<cmd>lua _LazygitToggle()<cr>",
				{ desc = "Run `lazygit` in a floating window." }
			)
		end,
	},
}
