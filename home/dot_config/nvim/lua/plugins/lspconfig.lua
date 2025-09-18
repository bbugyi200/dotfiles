-- P2: Look into getting LSP completion for vim.* functions!
-- P2: Add markdown LSP support!
-- P3: Configure clangd LSP server for work!
return {
	-- PLUGIN: http://github.com/neovim/nvim-lspconfig
	{
		"neovim/nvim-lspconfig",
		version = "*",
		dependencies = {
			"onsails/lspkind.nvim",
		},
		init = function()
			local bb = require("bb_utils")
			local cfg = require("lspconfig")

			if bb.is_goog_machine() then
				-- CiderLSP
				local configs = require("lspconfig.configs")
				local capabilities =
					require("cmp_nvim_lsp").default_capabilities(vim.lsp.protocol.make_client_capabilities())
				-- ─────────────────────────── configure ciderlsp ───────────────────────────
				local ciderlsp_filetypes = {
					"bzl",
					"c",
					"cpp",
					"dart",
					"go",
					"hgcommit",
					"html",
					"htmlangular",
					"java",
					"kotlin",
					"objc",
					"proto",
					"python",
					"rvl",
					"scss",
					"sql",
					"textproto",
					"txt",
				}

				configs.ciderlsp = {
					default_config = {
						cmd = {
							"/google/bin/releases/cider/ciderlsp/ciderlsp",
							"--tooltag=nvim-cmp",
							"--noforward_sync_responses",
						},
						filetypes = ciderlsp_filetypes,
						root_dir = cfg.util.root_pattern(".citc"),
						settings = {},
					},
				}

				cfg.ciderlsp.setup({
					capabilities = capabilities,
				})

				-- ───────────────────────── confgure analysislsp ──────────────────────
				configs.analysislsp = {
					default_config = {
						cmd = {
							"/google/bin/users/lerm/glint-ale/analysis_lsp/server",
							"--lint_on_save=false",
							"--max_qps=10",
						},
						filetypes = ciderlsp_filetypes,
						-- root_dir = lspconfig.util.root_pattern('BUILD'),
						root_dir = function(fname)
							return string.match(fname, "(/google/src/cloud/[%w_-]+/[%w_-]+/).+$")
						end,
						settings = {},
					},
				}

				cfg.analysislsp.setup({
					capabilities = capabilities,
				})
			else
				cfg.jedi_language_server.setup({
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
				cfg.ruff.setup({
					init_options = {
						settings = {
							-- Any extra CLI arguments for `ruff` go here.
							args = {},
						},
					},
				})
			end

			-- bash-language-server
			cfg.bashls.setup({
				filetypes = { "bash", "sh", "sh.chezmoitmpl", "zsh" },
				cmd = { "bash-language-server", "start" },
			})

			-- lua-language-server
			cfg.lua_ls.setup({
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

			-- vim-language-server
			cfg.vimls.setup({
				cmd = { "vim-language-server", "--stdio" },
				filetypes = { "vim" },
				root_dir = cfg.util.root_pattern("vimrc", ".vimrc", "package.json", ".git"),
			})
		end,
	},
}
