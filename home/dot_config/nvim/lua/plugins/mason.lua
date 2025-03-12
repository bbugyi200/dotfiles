--- A package manager used to install external editor tools for use within Neovim.
---
--- Allows you to easily manage external editor tooling such as LSP servers,
--- DAP servers, linters, and formatters through a single interface.

local mason_plugin_name = "williamboman/mason.nvim"
return {
	-- PLUGIN: http://github.com/williamboman/mason.nvim
	{
		mason_plugin_name,
		opts = {
			pip = { upgrade_pip = true },
		},
		lazy = false,
	},
	-- PLUGIN: http://github.com/williamboman/mason-lspconfig.nvim
	{
		"williamboman/mason-lspconfig.nvim",
		dependencies = mason_plugin_name,
		opts = {
			ensure_installed = {
				"bashls",
				"jedi_language_server",
				"lua_ls",
				"ruff",
				"vimls",
			},
		},
	},
	-- PLUGIN: http://github.com/WhoIsSethDaniel/mason-tool-installer.nvim
	{
		"WhoIsSethDaniel/mason-tool-installer.nvim",
		opts = {
			ensure_installed = {
				"black",
				"isort",
				"rustfmt",
				"shellcheck",
				"shfmt",
				"stylua",
			},
		},
	},
}
