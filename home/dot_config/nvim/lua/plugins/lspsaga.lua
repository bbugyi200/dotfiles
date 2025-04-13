--- Improves the Neovim built-in LSP experience.

return {
	-- PLUGIN: http://github.com/nvimdev/lspsaga.nvim
	{
		"nvimdev/lspsaga.nvim",
		opts = {},
		dependencies = {
			"nvim-treesitter/nvim-treesitter",
			"nvim-tree/nvim-web-devicons",
		},
	},
}
