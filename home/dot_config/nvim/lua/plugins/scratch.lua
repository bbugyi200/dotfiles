--- Create temporary playground files effortlessly. Find them later without worrying about filenames or locations.

local scratch_dir = vim.env.HOME .. "/tmp/scratch"

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
			filetypes = { "md", "sql", "txt", "zo" },
			scratch_file_dir = scratch_dir,
		},
		init = function()
			-- Create scratch_dir if it doesn't exist
			if vim.fn.isdirectory(scratch_dir) == 0 then
				vim.fn.mkdir(scratch_dir, "p")
			end

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP GROUP: <leader>f
			vim.keymap.set("n", "<leader>f", "<nop>", { desc = "scratch.nvim" })
			-- KEYMAP: <leader>ff
			vim.keymap.set("n", "<leader>ff", "<cmd>ScratchOpen<cr>", { desc = "Find an existing scratch file." })
			-- KEYMAP: <leader>fn
			vim.keymap.set("n", "<leader>fn", "<cmd>ScratchWithName<cr>", { desc = "Create a new named scratch file." })
			-- KEYMAP: <leader>fs
			vim.keymap.set(
				"n",
				"<leader>fs",
				"<cmd>ScratchOpenFzf<cr>",
				{ desc = "Search file contents of existing scratch files." }
			)
			-- KEYMAP: <leader>fu
			vim.keymap.set("n", "<leader>fu", "<cmd>Scratch<cr>", { desc = "Create a new unnamed scratch file." })
		end,
	},
}
