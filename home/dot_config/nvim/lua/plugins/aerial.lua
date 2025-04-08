--- Aerial is a tree-sitter based code outline view for Neovim.

return {
	-- PLUGIN: http://github.com/stevearc/aerial.nvim
	{
		"stevearc/aerial.nvim",
		opts = {},
		dependencies = {
			"nvim-treesitter/nvim-treesitter",
			"nvim-tree/nvim-web-devicons",
			-- For repeatable motions using { and }.
			"nvim-treesitter/nvim-treesitter-textobjects",
		},
		init = function()
			local aerial = require("aerial")
			local repeat_move = require("nvim-treesitter.textobjects.repeatable_move")

			local next_symbol, prev_symbol = repeat_move.make_repeatable_move_pair(aerial.next, aerial.prev)
			-- KEYMAP: {
			vim.keymap.set("n", "[{", prev_symbol, { desc = "Jump to previous Aerial symbol." })
			-- KEYMAP: }
			vim.keymap.set("n", "]}", next_symbol, { desc = "Jump to next Aerial symbol." })
			-- KEYMAP: <leader>o
			vim.keymap.set("n", "<leader>o", "<cmd>AerialToggle<cr>", {
				desc = "Toggle aerial.nvim outline window.",
			})
			-- KEYMAP: <leader>to
			vim.keymap.set("n", "<leader>to", "<cmd>Telescope aerial<cr>", { desc = "Telescope aerial" })
		end,
	},
}
