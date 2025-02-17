--- A clean, dark Neovim theme written in Lua, with support for lsp, treesitter and lots of plugins.

return {
	-- PLUGIN: http://github.com/folke/tokyonight.nvim
	{
		"folke/tokyonight.nvim",
		lazy = false,
		priority = 1000,
		opts = {},
		init = function()
			vim.cmd("colorscheme tokyonight")
		end,
	},
}
