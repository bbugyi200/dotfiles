---A Neovim plugin for moving around your code in a syntax tree aware manner.
local repeat_keymap = require("util.repeat_keymap")

return {
	-- PLUGIN: http://github.com/aaronik/treewalker.nvim
	{
		"aaronik/treewalker.nvim",
		opts = {},
		init = function()
			-- ┌────────────────────────────┐
			-- │ KEYMAPS FOR NAVIGATION.    │
			-- └────────────────────────────┘

			-- KEYMAP(N): <c-k>
			vim.keymap.set("n", "<c-k>", "<cmd>Treewalker Up<cr>", {
				desc = "Navigate to node above current node.",
			})
			-- KEYMAP(N): <c-j>
			vim.keymap.set("n", "<c-j>", "<cmd>Treewalker Down<cr>", {
				desc = "Navigate to node below current node.",
			})
			-- KEYMAP(N): <c-h>
			vim.keymap.set(
				"n",
				"<c-h>",
				"<cmd>Treewalker Left<cr>",
				{ desc = "Navigate to ancestor node above current node." }
			)
			-- KEYMAP(N): <c-l>
			vim.keymap.set(
				"n",
				"<c-l>",
				"<cmd>Treewalker Right<cr>",
				{ desc = "Navigate to child node below current node." }
			)

			-- ┌───────────────────────────
			-- │ KEYMAPS FOR SWAPPING.    │
			-- └───────────────────────────

			-- KEYMAP(N): <leader>xb
			repeat_keymap(
				"TreewalkerSwapDown",
				"<leader>xb",
				"<cmd>Treewalker SwapDown<cr>",
				{ desc = "Swap BIG node under cursor with next neighbor." }
			)
			-- KEYMAP(N): <leader>xB
			repeat_keymap("TreewalkerSwapUp", "<leader>xB", "<cmd>Treewalker SwapUp<cr>", {
				desc = "Swap BIG node under cursor with previous neighbor.",
			})
			-- KEYMAP(N): <leader>xs
			repeat_keymap("TreewalkerSwapRight", "<leader>xs", "<cmd>Treewalker SwapRight<cr>", {
				desc = "Swap SMALL node under cursor with next neighbor.",
			})
			-- KEYMAP(N): <leader>xS
			repeat_keymap("TreewalkerSwapLeft", "<leader>xS", "<cmd>Treewalker SwapLeft<cr>", {
				desc = "Swap SMALL node under cursor with previous neighbor.",
			})
		end,
	},
}
