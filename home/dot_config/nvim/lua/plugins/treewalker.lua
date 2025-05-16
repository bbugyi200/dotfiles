---A Neovim plugin for moving around your code in a syntax tree aware manner.
local bb = require("bb_utils")

return {
	-- PLUGIN: http://github.com/aaronik/treewalker.nvim
	{
		"aaronik/treewalker.nvim",
		opts = {},
		init = function()
			-- ┌────────────────────────────┐
			-- │ KEYMAPS FOR NAVIGATION.    │
			-- └────────────────────────────┘
			-- KEYMAP: <c-k>
			vim.keymap.set("n", "<c-k>", "<cmd>Treewalker Up<cr>", {
				desc = "Navigate to node above current node.",
			})
			-- KEYMAP: <c-j>
			vim.keymap.set("n", "<c-j>", "<cmd>Treewalker Down<cr>", {
				desc = "Navigate to node below current node.",
			})
			-- KEYMAP: <c-h>
			vim.keymap.set(
				"n",
				"<c-h>",
				"<cmd>Treewalker Left<cr>",
				{ desc = "Navigate to ancestor node above current node." }
			)
			-- KEYMAP: <c-l>
			vim.keymap.set(
				"n",
				"<c-l>",
				"<cmd>Treewalker Right<cr>",
				{ desc = "Navigate to child node below current node." }
			)

			-- ┌───────────────────────────
			-- │ KEYMAPS FOR SWAPPING.    │
			-- └───────────────────────────
			-- KEYMAP: <leader>xb
			bb.repeatable_nmap(
				"TreewalkerSwapDown",
				"<leader>xb",
				"<cmd>Treewalker SwapDown<cr>",
				{ desc = "Swap BIG node under cursor with next neighbor." }
			)
			-- KEYMAP: <leader>xB
			bb.repeatable_nmap("TreewalkerSwapUp", "<leader>xB", "<cmd>Treewalker SwapUp<cr>", {
				desc = "Swap BIG node under cursor with previous neighbor.",
			})
			-- KEYMAP: <leader>xs
			bb.repeatable_nmap("TreewalkerSwapRight", "<leader>xs", "<cmd>Treewalker SwapRight<cr>", {
				desc = "Swap SMALL node under cursor with next neighbor.",
			})
			-- KEYMAP: <leader>xS
			bb.repeatable_nmap("TreewalkerSwapLeft", "<leader>xS", "<cmd>Treewalker SwapLeft<cr>", {
				desc = "Swap SMALL node under cursor with previous neighbor.",
			})
		end,
	},
}
