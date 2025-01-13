-- P0: Install Telescope extensions!
--   [X] Install prochri/telescope-all-recent.nvim to sort 'buffers' by most recent!
--   [ ] Install extension for CodeSearch.
--   [ ] Use ,t<L> maps with Telescope builtins and extensions!
--   [ ] Install https://github.com/nvim-telescope/telescope-file-browser.nvim ?
return {
	{
		"nvim-telescope/telescope.nvim",
		branch = "0.1.x",
		dependencies = { "nvim-lua/plenary.nvim" },
		opts = {},
		init = function()
			local builtin = require("telescope.builtin")
			vim.keymap.set("n", "<space>", function()
				builtin.buffers()
			end, { desc = "Telescope buffers" })
			vim.keymap.set("n", "<leader>tb", function()
				builtin.buffers()
			end, { desc = "Telescope buffers" })
			vim.keymap.set("n", "<leader>tf", function()
				builtin.find_files()
			end, { desc = "Telescope find files" })
			vim.keymap.set("n", "<leader>tg", function()
				builtin.live_grep()
			end, { desc = "Telescope live grep" })
			vim.keymap.set("n", "<leader>th", function()
				builtin.help_tags()
			end, { desc = "Telescope help tags" })
		end,
	},
	{
		"prochri/telescope-all-recent.nvim",
		dependencies = {
			"kkharji/sqlite.lua",
		},
		opts = {
			pickers = {
				buffers = {
					disable = false,
					use_cwd = false,
					sorting = "frecency",
				},
			},
		},
	},
}
