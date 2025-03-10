--- A neovim lua plugin to help easily manage multiple terminal windows.

return {
	-- PLUGIN: http://github.com/akinsho/toggleterm.nvim
	{
		"akinsho/toggleterm.nvim",
		opts = {
			size = function(term)
				if term.direction == "horizontal" then
					return 20
				elseif term.direction == "vertical" then
					return vim.o.columns * 0.5
				end
			end,
		},
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

			-- KEYMAP(N): <leader>gl
			vim.keymap.set("n", "<leader>gl", function()
				lazygit:toggle()
			end, {
				desc = "Run `lazygit` in a floating window.",
			})
		end,
	},
}
