--- AI-powered coding, seamlessly in Neovim.

return {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		"olimorris/codecompanion.nvim",
		version = "*",
		dependencies = {
			{ "nvim-lua/plenary.nvim", branch = "master" },
			"nvim-treesitter/nvim-treesitter",
		},
		opts = {},
	},
}
