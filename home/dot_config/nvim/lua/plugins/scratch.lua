--- Create temporary playground files effortlessly. Find them later without worrying about filenames or locations.

return {
	-- PLUGIN: http://github.com/LintaoAmons/scratch.nvim
	{
		"LintaoAmons/scratch.nvim",
		dependencies = {
			{
				"ibhagwan/fzf-lua",
				dependencies = { "nvim-tree/nvim-web-devicons" },
				opts = {},
			},
		},
		opts = {
			filetypes = { "md", "txt", "zo" },
			scratch_file_dir = vim.env.HOME .. "/tmp/scratch",
		},
		init = function()
			-- KEYMAP GROUP: <leader>f
			vim.keymap.set("n", "<leader>f", "<nop>", { desc = "scratch.nvim" })
			-- KEYMAP: <leader>ff
			vim.keymap.set(
				"n",
				"<leader>ff",
				"<cmd>ScratchOpen<cr>",
				{ desc = "Search filenames for an existing scratch file." }
			)
			-- KEYMAP: <leader>fn
			vim.keymap.set("n", "<leader>fn", "<cmd>ScratchWithName<cr>", { desc = "Open a new named scratch file." })
			-- KEYMAP: <leader>fs
			vim.keymap.set(
				"n",
				"<leader>fs",
				"<cmd>ScratchOpenFzf<cr>",
				{ desc = "Search file contents for an existing scratch file." }
			)
			-- KEYMAP: <leader>fu
			vim.keymap.set("n", "<leader>fu", "<cmd>Scratch<cr>", { desc = "Open a new unnamed scratch file." })
		end,
	},
}
