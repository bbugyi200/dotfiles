--- Neovim file explorer: edit your filesystem like a buffer

return {
	-- PLUGIN: http://github.com/stevearc/oil.nvim
	{
		"stevearc/oil.nvim",
		opts = {},
		init = function()
			-- KEYMAP(C): o
			vim.cmd([[
        cabbrev o <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Oil" : "o"<CR>
      ]])
		end,
	},
}
