-- P0: Use different keymap (NOT <cr>) for accepting completion!
-- P1: Install more completion sources
--          (see https://github.com/hrsh7th/nvim-cmp/wiki/List-of-sources)!:
--   [ ] https://github.com/KadoBOT/cmp-plugins
--   [ ] https://github.com/garyhurtz/cmp_kitty
--   [ ] https://github.com/andersevenrud/cmp-tmux
return {
	"hrsh7th/nvim-cmp",
	dependencies = {
		"hrsh7th/cmp-buffer",
		"hrsh7th/cmp-nvim-lsp",
		"hrsh7th/cmp-nvim-lsp-signature-help",
		"hrsh7th/cmp-nvim-lua",
		"hrsh7th/cmp-path",
		"hrsh7th/cmp-cmdline",
		"dmitmel/cmp-cmdline-history",
	},
	init = function()
		vim.opt.completeopt = { "menu", "menuone", "noselect" }

		-- Don't show matching
		vim.opt.shortmess:append("c")

		local lspkind = require("lspkind")
		lspkind.init()

		local cmp = require("cmp")
		local luasnip = require("luasnip")

		cmp.setup({
			mapping = cmp.mapping.preset.insert({
				["<C-d>"] = cmp.mapping.scroll_docs(-4),
				["<C-u>"] = cmp.mapping.scroll_docs(4),
				["<C-e>"] = cmp.mapping.close(),
				["<C-Space>"] = cmp.mapping(cmp.mapping.complete(), { "i", "c" }),
				["<CR>"] = cmp.mapping(function(fallback)
					if cmp.visible() then
						if luasnip.expandable() then
							luasnip.expand()
						else
							cmp.confirm({
								select = true,
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
			}),

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

			sorting = {
				comparators = {}, -- We stop all sorting to let the lsp do the sorting
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
				native_menu = false,
				ghost_text = true,
			},
		})

		cmp.setup.cmdline({ "/", "?" }, {
			mapping = cmp.mapping.preset.cmdline(),
			sources = {
				{ name = "buffer" },
				{ name = "cmdline_history" },
			},
		})

		-- Use cmdline & path source for ':' (if you enabled `native_menu`, this won't work anymore).
		cmp.setup.cmdline(":", {
			mapping = cmp.mapping.preset.cmdline(),
			sources = cmp.config.sources({
				{ name = "path" },
			}, {
				{ name = "cmdline_history" },
				{ name = "cmdline" },
			}),
			matching = { disallow_symbol_nonprefix_matching = false },
		})

		-- P4: Remove this or add a comment to explain why it's here.
		vim.cmd([[
      augroup CmpZsh
        au!
        autocmd Filetype zsh lua require'cmp'.setup.buffer { sources = { { name = "zsh" }, } }
      augroup END
    ]])
	end,
}
