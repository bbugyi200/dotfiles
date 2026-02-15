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
		config = function()
			local bb = require("bb_utils")

			local servers = { "bashls", "just", "lua_ls", "vimls", "yamlls" }

			if bb.is_goog_machine() then
				-- CiderLSP
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
					"markdown",
					"objc",
					"proto",
					"python",
					"rvl",
					"scss",
					"sql",
					"textproto",
					"txt",
					"yaml",
				}

				vim.lsp.config("ciderlsp", {
					cmd = {
						"/google/bin/releases/cider/ciderlsp/ciderlsp",
						"--tooltag=nvim-cmp",
						"--noforward_sync_responses",
					},
					filetypes = ciderlsp_filetypes,
					root_dir = function(bufnr, on_dir)
						local root = vim.fs.root(bufnr, ".citc")
						if root then
							on_dir(root)
						end
					end,
					settings = {},
					capabilities = capabilities,
				})

				-- ───────────────────────── confgure analysislsp ──────────────────────
				vim.lsp.config("analysislsp", {
					cmd = {
						"/google/bin/users/lerm/glint-ale/analysis_lsp/server",
						"--lint_on_save=false",
						"--max_qps=10",
					},
					filetypes = ciderlsp_filetypes,
					root_dir = function(bufnr, on_dir)
						local fname = vim.api.nvim_buf_get_name(bufnr)
						local root = string.match(fname, "(/google/src/cloud/[%w_-]+/[%w_-]+/).+$")
						if root then
							on_dir(root)
						end
					end,
					settings = {},
					capabilities = capabilities,
				})

				table.insert(servers, "ciderlsp")
				table.insert(servers, "analysislsp")
			else
				vim.lsp.config("jedi_language_server", {
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
				vim.lsp.config("ruff", {
					init_options = {
						settings = {
							-- Any extra CLI arguments for `ruff` go here.
							args = {},
						},
					},
				})

				table.insert(servers, "jedi_language_server")
				table.insert(servers, "ruff")
			end

			-- bash-language-server
			vim.lsp.config("bashls", {
				filetypes = { "bash", "sh", "sh.chezmoitmpl", "zsh" },
				cmd = { "bash-language-server", "start" },
			})

			-- lua-language-server
			vim.lsp.config("lua_ls", {
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
			vim.lsp.config("vimls", {
				cmd = { "vim-language-server", "--stdio" },
				filetypes = { "vim" },
				root_markers = { "vimrc", ".vimrc", "package.json", ".git" },
			})

			-- yaml-language-server
			vim.lsp.config("yamlls", {
				settings = {
					yaml = {
						schemas = {
							[vim.fn.expand("~/.config/gai/gai.schema.json")] = "gai.yml",
							[vim.fn.expand("~/lib/gai/xprompts/workflow.schema.json")] = {
								"*/xprompts/**/*.yml",
								"*/.xprompts/**/*.yml",
							},
						},
						validate = true,
						schemaStore = {
							enable = true,
							url = "https://www.schemastore.org/api/json/catalog.json",
						},
					},
				},
			})

			vim.lsp.enable(servers)
		end,
	},
}
