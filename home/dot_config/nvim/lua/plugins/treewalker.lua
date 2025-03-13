---A Neovim plugin for moving around your code in a syntax tree aware manner.

return {
	-- PLUGIN: http://github.com/aaronik/treewalker.nvim
	{
		"aaronik/treewalker.nvim",
		opts = {},
		init = function()
			-- KEYMAP(N): <c-k>
			vim.keymap.set("n", "<c-k>", "<cmd>Treewalker Up<cr>", { desc = "Navigate to node above current node." })
			-- KEYMAP(N): <c-j>
			vim.keymap.set("n", "<c-j>", "<cmd>Treewalker Down<cr>", { desc = "Navigate to node below current node." })
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
		end,
	},
}
