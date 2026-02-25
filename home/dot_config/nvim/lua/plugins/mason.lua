--- A package manager used to install external editor tools for use within Neovim.
---
--- Allows you to easily manage external editor tooling such as LSP servers,
--- DAP servers, linters, and formatters through a single interface.

local mason_plugin_name = "williamboman/mason.nvim"
return {
	-- PLUGIN: http://github.com/williamboman/mason.nvim
	{
		mason_plugin_name,
		cmd = "Mason",
		event = "VeryLazy",
		opts = {
			pip = { upgrade_pip = true, install_args = { "--index-url", "https://pypi.org/simple/" } },
		},
		keys = {
			-- KEYMAP: <leader>ma
			{ "<leader>ma", "<cmd>Mason<cr>", desc = "Run :Mason command." },
		},
	},
	-- PLUGIN: http://github.com/williamboman/mason-lspconfig.nvim
	{
		"williamboman/mason-lspconfig.nvim",
		event = "VeryLazy",
		dependencies = { mason_plugin_name, "neovim/nvim-lspconfig" },
		opts = {
			ensure_installed = {
				"bashls",
				"jedi_language_server",
				"lua_ls",
				"ruff",
				"vimls",
				"yamlls",
			},
		},
	},
	-- PLUGIN: http://github.com/WhoIsSethDaniel/mason-tool-installer.nvim
	{
		"WhoIsSethDaniel/mason-tool-installer.nvim",
		event = "VeryLazy",
		dependencies = mason_plugin_name,
		opts = {
			ensure_installed = {
				"black",
				"isort",
				"prettier",
				"shellcheck",
				"shfmt",
				"stylua",
			},
		},
	},
	-- PLUGIN: http://github.com/jay-babu/mason-nvim-dap.nvim
	{
		"jay-babu/mason-nvim-dap.nvim",
		event = "VeryLazy",
		dependencies = { mason_plugin_name, "mfussenegger/nvim-dap" },
		opts = {
			ensure_installed = { "bash", "codelldb", "python" },
		},
	},
}
