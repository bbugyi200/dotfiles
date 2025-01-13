-- P2: Add markdown LSP support!
-- P3: Configure clangd LSP server for work!
return {
	"neovim/nvim-lspconfig",
	dependencies = {
		"onsails/lspkind.nvim",
	},
	init = function()
		-- Set desired filetypes from go/ciderlsp#supported
		-- To list all filetype names, see https://vi.stackexchange.com/a/14990
		local is_goog_machine = require("util.is_goog_machine").is_goog_machine
		local lspconfig = require("lspconfig")
		local configs = require("lspconfig.configs")

		configs.ciderlsp = {
			default_config = {
				cmd = {
					"/google/bin/releases/cider/ciderlsp/ciderlsp",
					"--tooltag=nvim-cmp",
					"--noforward_sync_responses",
				},
				filetypes = {
					"bzl",
					"c",
					"cpp",
					"dart",
					"go",
					"java",
					"kotlin",
					"objc",
					"proto",
					"python",
					"sql",
					"textproto",
				},
				root_dir = lspconfig.util.root_pattern(".citc"),
				settings = {},
			},
		}

		if is_goog_machine() then
			-- CiderLSP
			local client_capabilities = vim.lsp.protocol.make_client_capabilities()
			lspconfig.ciderlsp.setup({
				capabilities = require("cmp_nvim_lsp").default_capabilities(client_capabilities),
			})
		else
			lspconfig.jedi_language_server.setup({
				init_options = {
					completion = {
						disableSnippets = false,
						resolveEagerly = true,
					},
					diagnostics = {
						enable = true,
						didOpen = true,
						didChange = true,
						didSave = true,
					},
				},
			})
			lspconfig.ruff.setup({
				init_options = {
					settings = {
						-- Any extra CLI arguments for `ruff` go here.
						args = {},
					},
				},
			})
		end

		-- Bash configuration using bash-language-server
		lspconfig.bashls.setup({
			filetypes = { "sh", "bash", "zsh" },
			cmd = { "bash-language-server", "start" },
		})

		-- Rust configuration using rust-analyzer
		lspconfig.rust_analyzer.setup({
			settings = {
				["rust-analyzer"] = {
					checkOnSave = {
						command = "clippy",
					},
					procMacro = {
						enable = true,
					},
					cargo = {
						loadOutDirsFromCheck = true,
						allFeatures = true,
					},
				},
			},
		})

		-- lua-language-server
		lspconfig.lua_ls.setup({
			on_init = function(client)
				if client.workspace_folders then
					local path = client.workspace_folders[1].name
					if vim.loop.fs_stat(path .. "/.luarc.json") or vim.loop.fs_stat(path .. "/.luarc.jsonc") then
						return
					end
				end

				client.config.settings.Lua = vim.tbl_deep_extend("force", client.config.settings.Lua, {
					runtime = {
						-- Tell the language server which version of Lua you're using
						-- (most likely LuaJIT in the case of Neovim)
						version = "LuaJIT",
					},
					-- Make the server aware of Neovim runtime files
					workspace = {
						checkThirdParty = false,
						library = {
							vim.env.VIMRUNTIME,
							-- Depending on the usage, you might want to add additional paths here.
							-- "${3rd}/luv/library"
							-- "${3rd}/busted/library",
						},
					},
				})
			end,
			settings = {
				Lua = {},
			},
		})
	end,
}
