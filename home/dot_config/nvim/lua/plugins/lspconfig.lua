-- P2: Look into getting LSP completion for vim.* functions!
-- P2: Add markdown LSP support!
-- P3: Configure clangd LSP server for work!
return {
	-- PLUGIN: http://github.com/neovim/nvim-lspconfig
	{
		"neovim/nvim-lspconfig",
		dependencies = {
			"onsails/lspkind.nvim",
		},
		config = function()
			local bb = require("bb_utils")

			if bb.is_goog_machine() then
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

				vim.lsp.config("ciderlsp", {
					cmd = {
						"/google/bin/releases/cider/ciderlsp/ciderlsp",
						"--tooltag=nvim-cmp",
						"--noforward_sync_responses",
					},
					filetypes = ciderlsp_filetypes,
					root_dir = function(fname)
						return vim.fs.find(".citc", { path = fname, upward = true })[1]
					end,
					capabilities = capabilities,
				})
				vim.lsp.enable("ciderlsp")

				-- ───────────────────────── configure analysislsp ──────────────────────
				vim.lsp.config("analysislsp", {
					cmd = {
						"/google/bin/users/lerm/glint-ale/analysis_lsp/server",
						"--lint_on_save=false",
						"--max_qps=10",
					},
					filetypes = ciderlsp_filetypes,
					root_dir = function(fname)
						return string.match(fname, "(/google/src/cloud/[%w_-]+/[%w_-]+/).+$")
					end,
					capabilities = capabilities,
				})
				vim.lsp.enable("analysislsp")
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
				vim.lsp.enable("jedi_language_server")

				vim.lsp.config("ruff", {
					init_options = {
						settings = {
							-- Any extra CLI arguments for `ruff` go here.
							args = {},
						},
					},
				})
				vim.lsp.enable("ruff")
			end

			-- bash-language-server
			vim.lsp.config("bashls", {
				filetypes = { "bash", "sh", "sh.chezmoitmpl", "zsh" },
				cmd = { "bash-language-server", "start" },
			})
			vim.lsp.enable("bashls")

			-- lua-language-server
			vim.lsp.config("lua_ls", {
				on_init = function(client)
					if client.workspace_folders then
						local path = client.workspace_folders[1].name
						if vim.uv.fs_stat(path .. "/.luarc.json") or vim.uv.fs_stat(path .. "/.luarc.jsonc") then
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
			vim.lsp.enable("lua_ls")

			-- vim-language-server
			vim.lsp.config("vimls", {
				cmd = { "vim-language-server", "--stdio" },
				filetypes = { "vim" },
				root_dir = function(fname)
					local patterns = { "vimrc", ".vimrc", "package.json", ".git" }
					return vim.fs.find(patterns, { path = fname, upward = true })[1]
				end,
			})
			vim.lsp.enable("vimls")
		end,
	},
}
