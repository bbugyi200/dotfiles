--- A powerful Neovim plugin for managing MCP (Model Context Protocol) servers.

return {
	-- PLUGIN: http://github.com/ravitemer/mcphub.nvim
	{
		"ravitemer/mcphub.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim", -- Required for Job and HTTP requests
		},
		build = "npm install -g mcp-hub@latest",
		opts = {},
	},
}
