--- A completion plugin for neovim coded in Lua.
--
-- P2: Completion should appear in a separate window so ghost text is easier to see?!

local feedkeys = require("util.feedkeys")

return {
	-- PLUGIN: http://github.com/hrsh7th/nvim-cmp
	{
		"hrsh7th/nvim-cmp",
		dependencies = {
			-- PLUGIN: http://github.com/hrsh7th/cmp-buffer
			"hrsh7th/cmp-buffer",
			-- PLUGIN: http://github.com/hrsh7th/cmp-nvim-lsp
			"hrsh7th/cmp-nvim-lsp",
			-- PLUGIN: http://github.com/hrsh7th/cmp-nvim-lsp-signature-help
			"hrsh7th/cmp-nvim-lsp-signature-help",
			-- PLUGIN: http://github.com/hrsh7th/cmp-nvim-lua
			"hrsh7th/cmp-nvim-lua",
			-- PLUGIN: http://github.com/hrsh7th/cmp-path
			"hrsh7th/cmp-path",
			-- PLUGIN: http://github.com/dmitmel/cmp-cmdline-history
			"dmitmel/cmp-cmdline-history",
			-- PLUGIN: http://github.com/andersevenrud/cmp-tmux
			"andersevenrud/cmp-tmux",
			-- PLUGIN: http://github.com/rcarriga/cmp-dap
			"rcarriga/cmp-dap",
			-- PLUGIN: http://github.com/hrsh7th/cmp-emoji
			"hrsh7th/cmp-emoji",
			-- PLUGIN: http://github.com/petertriho/cmp-git
			{
				"petertriho/cmp-git",
				init = function()
					local format = require("cmp_git.format")
					local sort = require("cmp_git.sort")

					require("cmp_git").setup({
						gitlab = {},
						ssh_aliases = {},
						-- defaults
						filetypes = { "gitcommit", "octo", "NeogitCommitMessage" },
						remotes = { "upstream", "origin" }, -- in order of most to least prioritized
						-- enable git url rewrites, see
						-- https://git-scm.com/docs/git-config#Documentation/git-config.txt-urlltbasegtinsteadOf
						enableRemoteUrlRewrites = false,
						git = {
							commits = {
								limit = 100,
								sort_by = sort.git.commits,
								format = format.git.commits,
								sha_length = 7,
							},
						},
						github = {
							hosts = {}, -- list of private instances of github
							issues = {
								fields = { "title", "number", "body", "updatedAt", "state" },
								filter = "all", -- assigned, created, mentioned, subscribed, all, repos
								limit = 100,
								state = "open", -- open, closed, all
								sort_by = sort.github.issues,
								format = format.github.issues,
							},
							mentions = {
								limit = 100,
								sort_by = sort.github.mentions,
								format = format.github.mentions,
							},
							pull_requests = {
								fields = { "title", "number", "body", "updatedAt", "state" },
								limit = 100,
								state = "open", -- open, closed, merged, all
								sort_by = sort.github.pull_requests,
								format = format.github.pull_requests,
							},
						},
						trigger_actions = {
							{
								debug_name = "git_commits",
								trigger_character = ":",
								action = function(sources, trigger_char, callback, params, _)
									return sources.git:get_commits(callback, params, trigger_char)
								end,
							},
							{
								debug_name = "github_issues",
								trigger_character = "#",
								action = function(sources, trigger_char, callback, _, git_info)
									return sources.github:get_issues(callback, git_info, trigger_char)
								end,
							},
							{
								debug_name = "github_mentions",
								trigger_character = "@",
								action = function(sources, trigger_char, callback, _, git_info)
									return sources.github:get_mentions(callback, git_info, trigger_char)
								end,
							},
							{
								debug_name = "github_mrs",
								trigger_character = "!",
								action = function(sources, trigger_char, callback, _, git_info)
									return sources.github:get_merge_requests(callback, git_info, trigger_char)
								end,
							},
							{
								debug_name = "github_issues_and_pr",
								trigger_character = "#",
								action = function(sources, trigger_char, callback, _, git_info)
									return sources.github:get_issues_and_prs(callback, git_info, trigger_char)
								end,
							},
							{
								debug_name = "github_mentions",
								trigger_character = "@",
								action = function(sources, trigger_char, callback, _, git_info)
									return sources.github:get_mentions(callback, git_info, trigger_char)
								end,
							},
						},
					})
					table.insert(require("cmp").get_config().sources, { name = "git" })
				end,
			},
		},
		init = function()
			-- Don't show matching
			vim.opt.shortmess:append("c")

			local lspkind = require("lspkind")
			lspkind.init()

			local cmp = require("cmp")
			local luasnip = require("luasnip")

			cmp.setup({
				enabled = function()
					return vim.api.nvim_get_option_value("buftype", {}) ~= "prompt"
						or require("cmp_dap").is_dap_buffer()
				end,
				mapping = {
					["<C-d>"] = cmp.mapping.scroll_docs(-4),
					["<C-e>"] = cmp.mapping({
						i = cmp.mapping.abort(),
						c = cmp.mapping.close(),
					}),
					["<C-n>"] = cmp.mapping({
						c = function()
							if cmp.visible() then
								cmp.select_next_item({ behavior = cmp.SelectBehavior.Select })
							else
								feedkeys("<Down>")
							end
						end,
						i = function(fallback)
							if cmp.visible() then
								cmp.select_next_item({ behavior = cmp.SelectBehavior.Select })
							else
								fallback()
							end
						end,
					}),
					["<C-p>"] = cmp.mapping({
						c = function()
							if cmp.visible() then
								cmp.select_prev_item({ behavior = cmp.SelectBehavior.Select })
							else
								feedkeys("<Up>")
							end
						end,
						i = function(fallback)
							if cmp.visible() then
								cmp.select_prev_item({ behavior = cmp.SelectBehavior.Select })
							else
								fallback()
							end
						end,
					}),
					["<C-u>"] = cmp.mapping.scroll_docs(4),
					["<C-Space>"] = cmp.mapping(cmp.mapping.complete(), { "c", "i" }),
					["<CR>"] = cmp.mapping(function(fallback)
						-- See https://github.com/hrsh7th/nvim-cmp/wiki/Example-mappings#safely-select-entries-with-cr
						if cmp.visible() and cmp.get_active_entry() then
							if luasnip.expandable() then
								luasnip.expand()
							else
								cmp.confirm({
									select = true,
									behavior = cmp.ConfirmBehavior.Replace,
								})
							end
						else
							fallback()
						end
					end, { "c", "i" }),
					["<Tab>"] = cmp.mapping(function(fallback)
						if luasnip.expandable() then
							luasnip.expand()
						elseif luasnip.locally_jumpable(1) then
							luasnip.jump(1)
						elseif cmp.visible() then
							cmp.select_next_item()
						else
							fallback()
						end
					end, { "i", "s" }),
					["<S-Tab>"] = cmp.mapping(function(fallback)
						if luasnip.locally_jumpable(-1) then
							luasnip.jump(-1)
						elseif cmp.visible() then
							cmp.select_prev_item()
						else
							fallback()
						end
					end, { "i", "s" }),
				},
				sources = {
					{ name = "lazydev", group_index = 0 },
					{ name = "emoji", group_index = 0 },
					{ name = "googlers", max_item_count = 5, group_index = 1 }, -- go/cmp-googlers
					{ name = "nvim_lsp", group_index = 1 },
					{ name = "nvim_lsp_signature_help", group_index = 1 },
					{ name = "nvim_lua", group_index = 1 },
					{ name = "path", group_index = 1 },
					{ name = "copilot", group_index = 1 },
					{ name = "luasnip", group_index = 1 },
					{ name = "buffer", keyword_length = 3, group_index = 1 },
					{
						name = "tmux",
						group_index = 2,
						option = {
							all_panes = true,
							trigger_characters = { "." },
							trigger_characters_ft = {}, -- { filetype = { '.' } },
							capture_history = true,
						},
					},
					{ name = "buganizer", group_index = 2 }, -- go/cmp-buganizer
				},
				snippet = {
					expand = function(args)
						require("luasnip").lsp_expand(args.body)
					end,
				},
				formatting = {
					expandable_indicator = true,
					format = lspkind.cmp_format({
						with_text = true,
						maxwidth = 40, -- half max width
						menu = {
							buffer = "[buffer]",
							buganizer = "[bug]",
							cmdline_history = "[history]",
							copilot = "[copilot]",
							dap = "[dap]",
							git = "[git]",
							lazydev = "[lazydev]",
							luasnip = "[snip]",
							nvim_lsp = "[LSP]",
							nvim_lsp_signature_help = "[LSP:signature]",
							nvim_lua = "[API]",
							path = "[path]",
							tmux = "[tmux]",
						},
					}),
					fields = { "abbr", "kind", "menu" },
				},
				experimental = {
					ghost_text = true,
				},
			})

			-- Use buffer source for `/` and `?`.
			cmp.setup.cmdline({ "/", "?" }, {
				completion = { autocomplete = false },
				sources = {
					{ name = "cmdline_history" },
				},
				matching = {
					disallow_fullfuzzy_matching = true,
					disallow_fuzzy_matching = true,
					disallow_partial_fuzzy_matching = true,
					disallow_partial_matching = true,
					disallow_prefix_unmatching = true,
					disallow_symbol_nonprefix_matching = true,
				},
			})

			-- Use cmdline & path source for ':' (if you enabled `native_menu`, this won't work anymore).
			cmp.setup.cmdline(":", {
				completion = { autocomplete = false },
				sources = cmp.config.sources({
					{ name = "cmdline_history" },
				}),
				matching = {
					disallow_fuzzy_matching = true,
					disallow_fullfuzzy_matching = true,
					disallow_partial_fuzzy_matching = true,
					disallow_partial_matching = true,
					disallow_prefix_unmatching = true,
					disallow_symbol_nonprefix_matching = true,
				},
			})

			cmp.setup.filetype({
				"dap-repl",
				"dapui_watches",
				"dapui_hover",
			}, { sources = { name = "dap" } })
		end,
	},
}
