return {
	"akinsho/bufferline.nvim",
	version = "*",
	dependencies = "nvim-tree/nvim-web-devicons",
	init = function()
		vim.opt.termguicolors = true
		require("bufferline").setup({
			options = {
				numbers = "buffer_id",
				diagnostics = "nvim_lsp",
				diagnostics_update_on_event = true,
				diagnostics_indicator = function(count, _, _, _)
					return "(" .. count .. ")"
				end,
				show_buffer_close_icons = false,
				offsets = { filetype = "NvimTree", text = "File Explorer", text_align = "left", separator = true },
			},
		})
	end,
}
