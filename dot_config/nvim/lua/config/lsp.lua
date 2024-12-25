-- CiderLSP

-- 1. Configure CiderLSP
-- Set desired filetypes from go/ciderlsp#supported
-- To list all filetype names, see https://vi.stackexchange.com/a/14990
local nvim_lsp = require("lspconfig")
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
		root_dir = nvim_lsp.util.root_pattern(".citc"),
		settings = {},
	},
}

-- 2. Configure CMP
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
		{ name = "nvim_lua" },
		{ name = "path" },
		{ name = "luasnip" },
		{ name = "luasnip_choice" },
		{ name = "buffer", keyword_length = 5 },
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
				nvim_lsp = "[LSP]",
				nvim_lua = "[API]",
				path = "[path]",
				luasnip = "[snip]",
				luasnip_choice = "[snip:choice]",
				cmdline = "[command]",
				cmdline_history = "[history]",
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

vim.cmd([[
  augroup CmpZsh
    au!
    autocmd Filetype zsh lua require'cmp'.setup.buffer { sources = { { name = "zsh" }, } }
  augroup END
]])

-- CiderLSP
nvim_lsp.ciderlsp.setup({
	capabilities = require("cmp_nvim_lsp").default_capabilities(vim.lsp.protocol.make_client_capabilities()),
})

-- lua-language-server
nvim_lsp.lua_ls.setup({
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
				-- or pull in all of 'runtimepath'. NOTE: this is a lot slower and will cause issues when working on your own configuration (see https://github.com/neovim/nvim-lspconfig/issues/3189)
				-- library = vim.api.nvim_get_runtime_file("", true)
			},
		})
	end,
	settings = {
		Lua = {},
	},
})
