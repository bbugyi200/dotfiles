return {
	"folke/which-key.nvim",
	event = "VeryLazy",
	opts = {
		-- NOTE: Removing 'x' from 'mode' seems to fix an issue with
		--   linewise-visual (V) mode when using a <count>, but I've decided not to
		--   use this linewise-visual mode for now since it seems to be buggy (stops
		--   working after using it with snippets).
		triggers = { "<auto>", mode = "nisotcx" },
	},
	keys = {
		{
			"<leader>?",
			function()
				require("which-key").show({ global = false })
			end,
			desc = "Buffer Local Keymaps (which-key)",
		},
	},
}
