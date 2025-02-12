--- lazydev.nvim is a plugin that properly configures LuaLS for editing your Neovim config by lazily updating your workspace libraries.

return {
	-- PLUGIN: http://github.com/folke/lazydev.nvim
	{
		"folke/lazydev.nvim",
		ft = "lua", -- Only load for Lua files.
		opts = {},
	},
}
