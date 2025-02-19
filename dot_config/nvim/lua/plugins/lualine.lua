-- P2: Get line/column number on bottom buffer tab back (with lualine?).
return {
	-- PLUGIN: http://github.com/nvim-lualine/lualine.nvim
	{
		"nvim-lualine/lualine.nvim",
		dependencies = { "nvim-tree/nvim-web-devicons" },
		init = function()
			local custom_tokyo = require("lualine.themes.tokyonight")
			custom_tokyo.inactive.c = { fg = "#1f2335", bg = "#828bb8", gui = "bold" }
			require("lualine").setup({
				options = {
					icons_enabled = true,
					theme = custom_tokyo,
					component_separators = { left = "", right = "" },
					section_separators = { left = "", right = "" },
					ignore_focus = {},
					always_divide_middle = true,
					always_show_tabline = true,
					globalstatus = false,
					refresh = {
						statusline = 100,
						tabline = 100,
						winbar = 100,
					},
				},
				sections = {
					lualine_a = { "mode" },
					lualine_b = { "branch", "diff", "diagnostics" },
					lualine_c = {
						{ "filename", path = 1 },
						{ "aerial", colored = true },
					},
					lualine_x = {
						{ "copilot", show_colors = true },
						"filetype",
					},
					lualine_y = { "progress" },
					lualine_z = { "location" },
				},
				inactive_sections = {
					lualine_a = {},
					lualine_b = {},
					lualine_c = {
						{ "filename", path = 1 },
					},
					lualine_x = {},
					lualine_y = {},
					lualine_z = {},
				},
				tabline = {},
				winbar = {},
				inactive_winbar = {},
				extensions = { "aerial", "fugitive", "man", "quickfix" },
			})
		end,
	},
}
