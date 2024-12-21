return {
	"neovim/nvim-lspconfig",
	dependencies = {
		"onsails/lspkind.nvim",
		{
			"folke/trouble.nvim",
			dependencies = {
				"nvim-tree/nvim-web-devicons",
			},
		},
	},
}
