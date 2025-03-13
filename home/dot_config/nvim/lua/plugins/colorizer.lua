--- The fastest Neovim colorizer.

return {
	-- PLUGIN: http://github.com/catgoose/nvim-colorizer.lua
	{
		"catgoose/nvim-colorizer.lua",
		opts = {
			filetypes = { "*" },
			user_default_options = { mode = "virtualtext" },
		},
	},
}
