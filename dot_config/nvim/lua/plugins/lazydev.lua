--- Properly configures LuaLS for editing your Neovim config (integrates with lspconfig).

return {
	-- PLUGIN: http://github.com/folke/lazydev.nvim
	{
		"folke/lazydev.nvim",
		ft = "lua", -- Only load for Lua files.
		opts = {},
	},
}
