--- Fancy and Blazing Fast start screen plugin of neovim.

return {
	-- PLUGIN: http://github.com/nvimdev/dashboard-nvim
	{
		"nvimdev/dashboard-nvim",
		event = "VimEnter",
		dependencies = { "nvim-tree/nvim-web-devicons" },
		opts = {
			theme = "hyper",
			config = {
				week_header = {
					enable = true,
				},
				shortcut = {
					{ desc = "󰊳 Update", group = "@property", action = "Lazy update", key = "u" },
					{
						icon = " ",
						icon_hl = "@variable",
						desc = "Files",
						group = "Label",
						action = "Telescope find_files",
						key = "f",
					},
					{
						desc = " dotfiles",
						group = "Number",
						action = "Telescope chezmoi find_files",
						key = "d",
					},
					{
						desc = " Sessions",
						group = "DiagnosticHint",
						action = "Autosession search",
						key = "s",
					},
					{
						desc = "❌ Quit",
						action = "quit",
						key = "q",
					},
				},
			},
		},
	},
}
