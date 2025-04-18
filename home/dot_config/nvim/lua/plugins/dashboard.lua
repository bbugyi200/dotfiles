--- Fancy and Blazing Fast start screen plugin of neovim.

local is_goog_machine = require("util.is_goog_machine")

return {
	-- PLUGIN: http://github.com/nvimdev/dashboard-nvim
	{
		"nvimdev/dashboard-nvim",
		event = "VimEnter",
		dependencies = { "nvim-tree/nvim-web-devicons" },
		config = function()
			require("dashboard").setup({
				theme = "hyper",
				config = {
					week_header = {
						enable = true,
					},
					shortcut = {
						{
							desc = "🔭 CodeSearch",
							enable = is_goog_machine(),
							action = "Telescope codesearch find_query",
							key = "c",
						},
						{
							desc = " dotfiles",
							group = "Number",
							action = "Telescope chezmoi find_files",
							key = "d",
						},
						{
							icon = " ",
							icon_hl = "@variable",
							desc = "Files",
							group = "Label",
							action = "Telescope find_files",
							key = "f",
						},
						{
							desc = " Sessions",
							group = "@function",
							action = "Autosession search",
							key = "s",
						},
						{ desc = "󰊳 Update", group = "@property", action = "Lazy update", key = "u" },
						{
							desc = "❌ Quit",
							group = "ErrorMsg",
							action = "quit",
							key = "q",
						},
					},
				},
			})
		end,
	},
}
