--- A clean, dark Neovim theme written in Lua, with support for lsp, treesitter and lots of plugins.

return {
	-- PLUGIN: http://github.com/folke/tokyonight.nvim
	{
		"folke/tokyonight.nvim",
		lazy = false,
		priority = 1000,
		opts = { dim_inactive = false, hide_inactive_statusline = false },
		init = function()
			vim.cmd("colorscheme tokyonight")
			vim.cmd("highlight winseparator guibg=none, guifg=#888888")
		end,
	},
}
