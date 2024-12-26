return {
	"akinsho/bufferline.nvim",
	version = "*",
	dependencies = "nvim-tree/nvim-web-devicons",
	init = function()
		vim.opt.termguicolors = true
		require("bufferline").setup({})
	end,
	opts = {
		options = { numbers = "buffer_id" },
	},
}
