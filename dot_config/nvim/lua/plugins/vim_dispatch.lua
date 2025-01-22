--- Dispatches shell commands asynchronously.

local dispatch_plugin_name = "tpope/vim-dispatch"
return {
	-- PLUGIN: http://github.com/tpope/vim-dispatch
	{ dispatch_plugin_name, enabled = true },
	-- PLUGIN: http://github.com/radenling/vim-dispatch-neovim
	{ "radenling/vim-dispatch-neovim", dependencies = dispatch_plugin_name },
}
