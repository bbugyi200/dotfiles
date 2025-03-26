--- Overloaded ; and , keys in Neovim.

return {
	-- PLUGIN: http://github.com/mawkler/demicolon.nvim
	{
		"mawkler/demicolon.nvim",
		dependencies = {
			"nvim-treesitter/nvim-treesitter",
			"nvim-treesitter/nvim-treesitter-textobjects",
		},
		opts = {
			keymaps = { repeat_motions = false },
		},
	},
}
