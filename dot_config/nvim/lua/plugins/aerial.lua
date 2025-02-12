--- Aerial is a tree-sitter based code outline view for Neovim.

return {
	-- PLUGIN: http://github.com/stevearc/aerial.nvim
	{
		"stevearc/aerial.nvim",
		opts = {},
		dependencies = {
			"nvim-treesitter/nvim-treesitter",
			"nvim-tree/nvim-web-devicons",
		},
		init = function()
			-- KEYMAP(N): <leader>o
			vim.keymap.set("n", "<leader>o", "<cmd>AerialToggle<cr>", {
				desc = "Toggle aerial.nvim outline window.",
			})
			-- KEYMAP(N): <leader>to
			vim.keymap.set("n", "<leader>to", "<cmd>Telescope aerial<cr>", { desc = "Telescope aerial" })
		end,
		on_attach = function(bufnr)
			-- KEYMAP(N): {
			vim.keymap.set(
				"n",
				"{",
				"<cmd>AerialPrev<CR>",
				{ buffer = bufnr, desc = "Jump to previous Aerial symbol." }
			)
			-- KEYMAP(N): }
			vim.keymap.set("n", "}", "<cmd>AerialNext<CR>", { buffer = bufnr, desc = "Jump to next Aerial symbol." })
		end,
	},
}
