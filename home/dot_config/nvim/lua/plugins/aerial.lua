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
			-- KEYMAP: {
			vim.keymap.set("n", "[{", "<cmd>AerialPrev<CR>", { desc = "Jump to previous Aerial symbol." })
			-- KEYMAP: }
			vim.keymap.set("n", "]}", "<cmd>AerialNext<CR>", { desc = "Jump to next Aerial symbol." })
			-- KEYMAP: <leader>o
			vim.keymap.set("n", "<leader>o", "<cmd>AerialToggle<cr>", {
				desc = "Toggle aerial.nvim outline window.",
			})
			-- KEYMAP: <leader>to
			vim.keymap.set("n", "<leader>to", "<cmd>Telescope aerial<cr>", { desc = "Telescope aerial" })
		end,
	},
}
