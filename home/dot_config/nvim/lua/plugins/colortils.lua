--- Some color utils for Neovim.

return {
	-- PLUGIN: http://github.com/max397574/colortils.nvim
	{
		"max397574/colortils.nvim",
		cmd = "Colortils",
		opts = {},
		init = function()
			-- KEYMAP: <leader>ct
			vim.keymap.set(
				"n",
				"<leader>ct",
				"<cmd>Colortils picker <c-r><c-w><cr>",
				{ desc = "Open colortils picker using color under cursor." }
			)
		end,
	},
}
