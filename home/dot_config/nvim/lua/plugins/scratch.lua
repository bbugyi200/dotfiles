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
			filetypes = { "dart", "java", "md", "py", "sh", "txt", "zo" },
			scratch_file_dir = vim.env.HOME .. "/tmp/scratch",
		},
		init = function()
			-- KEYMAP GROUP: <leader>f
			vim.keymap.set("n", "<leader>f", "<nop>", { desc = "scratch.nvim" })
			-- KEYMAP: <leader>ff
			vim.keymap.set("n", "<leader>ff", "<cmd>Scratch<cr>", { desc = "Open a new unnamed scratch file." })
			-- KEYMAP: <leader>fF
			vim.keymap.set("n", "<leader>fF", "<cmd>ScratchWithName<cr>", { desc = "Open a new named scratch file." })
			-- KEYMAP: <leader>fo
			vim.keymap.set(
				"n",
				"<leader>fo",
				"<cmd>ScratchOpen<cr>",
				{ desc = "Search filenames for an existing scratch file." }
			)
			-- KEYMAP: <leader>fO
			vim.keymap.set(
				"n",
				"<leader>fO",
				"<cmd>ScratchOpenFzf<cr>",
				{ desc = "Search file contents for an existing scratch file." }
			)
		end,
	},
}
