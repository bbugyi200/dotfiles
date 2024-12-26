return {
	"akinsho/bufferline.nvim",
	version = "*",
	dependencies = "nvim-tree/nvim-web-devicons",
	init = function()
		vim.opt.termguicolors = true
		require("bufferline").setup({
			highlights = {
				buffer_selected = { fg = "yellow", bg = "black" },
				buffer_visible = { fg = "darkyellow", bg = "black" },
				warning_diagnostic_selected = { fg = "yellow", bg = "black" },
				warning_diagnostic_visible = { fg = "darkyellow", bg = "black" },
			},
			options = {
				numbers = "buffer_id",
				show_buffer_close_icons = false,
				offsets = { { filetype = "NvimTree", text = "File Explorer", text_align = "left", separator = true } },
			},
		})
	end,
}
