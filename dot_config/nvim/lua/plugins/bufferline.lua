-- P3: Improve https://github.com/akinsho/bufferline.nvim!
--   [ ] Make bufferline buffers use less space!
--   [ ] Group buffers by extension
--   [ ] Add :BufferLinePick map for splits and tabs!
--   [ ] Use :BufferLineCycleNext for ]b!
--   [ ] Add mappings to close all buffers, left buffers, and right buffers!
--   [ ] Use ordinal numbers instead of buffer numbers?
--   [ ] Figure out how to get diagnostics WITHOUT breaking highlighting!
return {
	"akinsho/bufferline.nvim",
	version = "*",
	dependencies = "nvim-tree/nvim-web-devicons",
	init = function()
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
