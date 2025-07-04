-- P3: Improve https://github.com/akinsho/bufferline.nvim!
--   [ ] Make bufferline buffers use less space!
--   [ ] Group buffers by extension
--   [ ] Add :BufferLinePick map for splits and tabs!
--   [ ] Use :BufferLineCycleNext for ]b!
--   [ ] Add mappings to close all buffers, left buffers, and right buffers!
--   [ ] Use ordinal numbers instead of buffer numbers?
--   [ ] Figure out how to get diagnostics WITHOUT breaking highlighting!
return {
	-- PLUGIN: http://github.com/akinsho/bufferline.nvim
	{
		"akinsho/bufferline.nvim",
		version = "*",
		dependencies = {
			"nvim-tree/nvim-web-devicons",
			"folke/tokyonight.nvim", -- Since we are using tokyonight colors.
		},
		init = function()
			local tokyo_colors = require("tokyonight.colors").setup()
			local tokyo_utils = require("tokyonight.util")

			local dark_yellow = tokyo_utils.darken(tokyo_colors.yellow, 0.7)
			require("bufferline").setup({
				highlights = {
					buffer_selected = { fg = tokyo_colors.yellow, bg = tokyo_colors.black },
					buffer_visible = { fg = dark_yellow, bg = tokyo_colors.black },
					tab = { fg = tokyo_colors.yellow, bg = tokyo_colors.black },
					tab_selected = { fg = tokyo_colors.black, bg = tokyo_colors.yellow },
					warning_diagnostic_selected = { fg = tokyo_colors.black, bg = tokyo_colors.yellow },
					warning_diagnostic_visible = { fg = dark_yellow, bg = tokyo_colors.black },
				},
				options = {
					numbers = "buffer_id",
					show_buffer_close_icons = false,
					offsets = {
						{
							filetype = "aerial",
							text = "AERIAL",
						},
						{
							filetype = "bufexplorer",
							text = "BUFEXPLORER",
						},
						{
							filetype = "codecompanion",
							text = "CODE COMPANION",
						},
						{
							filetype = "help",
							text = "HELP",
						},
						{
							filetype = "neotest-summary",
							text = "NEOTEST (summary)",
						},
						{
							filetype = "neotest-output-panel",
							text = "NEOTEST (output)",
						},
						{
							filetype = "netrw",
							text = "FILE EXPLORER",
						},
						{
							filetype = "query",
							text = "TREESITTER",
						},
						{
							filetype = "sagaoutline",
							text = "LSPSAGA",
						},
					},
				},
			})
		end,
	},
}
