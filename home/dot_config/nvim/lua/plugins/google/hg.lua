--- Plugins for working with fig (aka the 'hg' command).
---
--- * hg.nvim provides fugitive.vim like integration for google internal fig.
--- * figtree: an opinionated interface for Fig in Neovim, designed to make
---     your workflow more efficient.

return {
	-- PLUGIN: http://go/hg.nvim
	{
		url = "sso://googler@user/smwang/hg.nvim",
		dependencies = {
			{
				"ipod825/libp.nvim",
				opts = {},
			},
			"nvim-lua/plenary.nvim",
		},
		lazy = false,
		opts = {},
	},
	-- PLUGIN: http://go/figtree
	{
		name = "figtree",
		url = "sso://user/jackcogdill/nvim-figtree",
		opts = {},
		init = function()
			-- KEYMAP: <leader>h
			vim.keymap.set("n", "<leader>h", function()
				require("figtree").toggle()
			end, { desc = "Open figtree view." })
		end,
	},
}
