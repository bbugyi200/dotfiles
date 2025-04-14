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
		},
	},
}
