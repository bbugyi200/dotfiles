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
			local repeat_move = require("nvim-treesitter-textobjects.repeatable_move")

			local move_symbol = repeat_move.make_repeatable_move(function(opts)
				if opts.forward then
					aerial.next()
				else
					aerial.prev()
				end
			end)
			-- KEYMAP: {
			vim.keymap.set("n", "[{", function()
				move_symbol({ forward = false })
			end, { desc = "Jump to previous Aerial symbol." })
			-- KEYMAP: }
			vim.keymap.set("n", "]}", function()
				move_symbol({ forward = true })
			end, { desc = "Jump to next Aerial symbol." })
			-- KEYMAP: <leader>ae
			vim.keymap.set("n", "<leader>ae", "<cmd>AerialToggle<cr>", {
				desc = "Toggle aerial.nvim outline window.",
			})
			-- KEYMAP: <leader>tae
			vim.keymap.set("n", "<leader>tae", "<cmd>Telescope aerial<cr>", { desc = "Telescope aerial" })
		end,
	},
}
