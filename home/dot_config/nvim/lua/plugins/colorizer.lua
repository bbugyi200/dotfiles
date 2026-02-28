--- The fastest Neovim colorizer.

return {
	-- PLUGIN: http://github.com/catgoose/nvim-colorizer.lua
	{
		"catgoose/nvim-colorizer.lua",
		opts = {
			filetypes = { "*" },
			options = {
				display = {
					mode = "virtualtext",
				},
			},
		},
	},
}
