-- P2: Completion should appear in a separate window so ghost text is easier to see?!
-- P2: Install more completion sources
--          (see https://github.com/hrsh7th/nvim-cmp/wiki/List-of-sources)!:
--   [ ] https://github.com/KadoBOT/cmp-plugins
--   [ ] https://github.com/garyhurtz/cmp_kitty
--   [ ] https://github.com/andersevenrud/cmp-tmux
--   [ ] https://github.com/petertriho/cmp-git

--- Replace termcodes (ex: "<Up>" or "<Down>") in a string so it can be used with `nvim_feedkeys`.
---
--- See https://neovim.io/doc/user/api.html#nvim_replace_termcodes() and/or
--- https://neovim.io/doc/user/api.html#nvim_feedkeys() for more information.
---
---@param keys string The keys to replace termcodes in.
---@return string # The keys with termcodes replaced.
local function replace_termcodes(keys)
	return vim.api.nvim_replace_termcodes(keys, true, true, true)
end

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
			-- PLUGIN: http://github.com/hrsh7th/cmp-cmdline
			"hrsh7th/cmp-cmdline",
			-- PLUGIN: http://github.com/dmitmel/cmp-cmdline-history
			"dmitmel/cmp-cmdline-history",
		},
		init = function()
			-- Don't show matching
			vim.opt.shortmess:append("c")

			local lspkind = require("lspkind")
			lspkind.init()

			local cmp = require("cmp")
			local luasnip = require("luasnip")

			cmp.setup({
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
								vim.api.nvim_feedkeys(replace_termcodes("<Up>"), "n", true)
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
								vim.api.nvim_feedkeys(replace_termcodes("<Down>"), "n", true)
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
					["<C-Space>"] = cmp.mapping(cmp.mapping.complete(), { "i", "c" }),
					["<CR>"] = cmp.mapping(function(fallback)
						-- See https://github.com/hrsh7th/nvim-cmp/wiki/Example-mappings#safely-select-entries-with-cr
						if cmp.visible() and cmp.get_active_entry() then
							if luasnip.expandable() then
								luasnip.expand()
							else
								cmp.confirm({
									behavior = cmp.ConfirmBehavior.Replace,
									select = false,
								})
							end
						else
							fallback()
						end
					end),
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
					{ name = "nvim_lsp" },
					{ name = "nvim_lsp_signature_help" },
					{ name = "nvim_lua" },
					{ name = "copilot" },
					{ name = "path" },
					{ name = "luasnip" },
					{ name = "buffer", keyword_length = 3 },
					{ name = "buganizer" },
				},
				snippet = {
					expand = function(args)
						require("luasnip").lsp_expand(args.body)
					end,
				},
				formatting = {
					format = lspkind.cmp_format({
						with_text = true,
						maxwidth = 40, -- half max width
						menu = {
							buffer = "[buffer]",
							buganizer = "[bug]",
							cmdline = "[command]",
							cmdline_history = "[history]",
							copilot = "[copilot]",
							luasnip = "[snip]",
							nvim_lsp = "[LSP]",
							nvim_lsp_signature_help = "[LSP:signature]",
							nvim_lua = "[API]",
							path = "[path]",
						},
					}),
				},
				experimental = {
					ghost_text = true,
				},
			})

			-- Use buffer source for `/` and `?`.
			cmp.setup.cmdline({ "/", "?" }, {
				completion = { autocomplete = false },
				mapping = cmp.mapping.preset.cmdline(),
				sources = {
					{ name = "cmdline_history" },
					{ name = "buffer" },
				},
				matching = {
					disallow_fuzzy_matching = true,
					disallow_fullfuzzy_matching = true,
					disallow_partial_fuzzy_matching = true,
					disallow_partial_matching = true,
					disallow_prefix_unmatching = true,
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
				},
			})
		end,
	},
}
