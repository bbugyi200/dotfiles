--- Use your Neovim like using Cursor AI IDE!

return {
	-- PLUGIN: http://github.com/yetone/avante.nvim
	{
		"yetone/avante.nvim",
		build = "make",
		dependencies = {
			"nvim-treesitter/nvim-treesitter",
			"stevearc/dressing.nvim",
			"nvim-lua/plenary.nvim",
			"MunifTanjim/nui.nvim",
		},
		event = "VeryLazy",
		version = false,
		opts = {},
	},
}
