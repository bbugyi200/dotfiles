--- A powerful Neovim plugin for managing MCP (Model Context Protocol) servers.

return {
	-- PLUGIN: http://github.com/ravitemer/mcphub.nvim
	{
		"ravitemer/mcphub.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim", -- Required for Job and HTTP requests
		},
		-- WARNING: Since `npm -g` without `sudo` doesn't work, you'll need to run
		-- `sudo npm install -g mcp-hub@latest` manually on your system before
		-- installing this plugin.
		--
		-- build = "npm install -g mcp-hub@latest",
		opts = {},
	},
}
