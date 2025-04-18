--- Google completion plugins (aka cmp-* plugins) live here.
---
--- * cmp-buganizer: Add autocomplete when typing b/, BUG=, and FIXED=.
--- * cmp-googlers: A Neovim plugin that provides dynamic user completion using
---     nvim-cmp. It allows for custom user retrieval functions, making it flexible
---     for various use cases such as mentioning users in comments or
---     documentation.
--- * cmp-nvim-ciderlsp: source for integrating ciderLSP ML-completion which
---     uses a request method $/textDocument/inlineCompletion which is not part of
---     the LSP.

return {
	-- PLUGIN: http://go/cmp-buganizer
	{
		url = "sso://user/vicentecaycedo/cmp-buganizer",
		cond = function()
			return vim.fn.executable("bugged") == 1
		end,
		config = function(_, opts)
			local cmp_buganizer = require("cmp-buganizer")
			cmp_buganizer.setup(opts)
		end,
		opts = {},
	},
	-- PLUGIN: http://go/cmp-googlers
	{
		"vintharas/cmp-googlers.nvim",
		dependencies = { "hrsh7th/nvim-cmp" },
		url = "sso://user/vintharas/cmp-googlers.nvim",
		opts = {},
	},
	-- PLUGIN: https://user.git.corp.google.com/piloto/cmp-nvim-ciderlsp
	{
		url = "sso://user/piloto/cmp-nvim-ciderlsp",
		opts = {
			override_trigger_characters = true, -- optional, to trigger non-ML more often
		},
		event = "LspAttach", -- load this plugin lazily only when LSP is being used
	},
}
