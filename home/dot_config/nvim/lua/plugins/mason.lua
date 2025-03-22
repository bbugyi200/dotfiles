--- A package manager used to install external editor tools for use within Neovim.
---
--- Allows you to easily manage external editor tooling such as LSP servers,
--- DAP servers, linters, and formatters through a single interface.

local mason_plugin_name = "williamboman/mason.nvim"
return {
	-- PLUGIN: http://github.com/williamboman/mason.nvim
	{
		mason_plugin_name,
		lazy = false,
		opts = {
			pip = { upgrade_pip = true },
		},
		init = function()
			-- KEYMAP(N): <leader>ma
			vim.keymap.set("n", "<leader>ma", "<cmd>Mason<cr>", { desc = "Run :Mason command." })
		end,
	},
	-- PLUGIN: http://github.com/williamboman/mason-lspconfig.nvim
	{
		"williamboman/mason-lspconfig.nvim",
		dependencies = { mason_plugin_name, "neovim/nvim-lspconfig" },
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
		dependencies = mason_plugin_name,
		opts = {
			ensure_installed = {
				"black",
				"isort",
				"shellcheck",
				"shfmt",
				"stylua",
			},
		},
	},
	-- PLUGIN: http://github.com/jay-babu/mason-nvim-dap.nvim
	{
		"jay-babu/mason-nvim-dap.nvim",
		dependencies = { mason_plugin_name, "mfussenegger/nvim-dap" },
		opts = {
			ensure_installed = { "bash", "cppdbg", "python" },
		},
	},
}
