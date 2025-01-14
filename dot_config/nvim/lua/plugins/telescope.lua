-- P0: Install Telescope extensions!
--   [X] Install prochri/telescope-all-recent.nvim to sort 'buffers' by most recent!
--   [X] Use ,t<L> maps with Telescope builtins and extensions!
--   [ ] Explore all extensions highlighted in file:///Users/bbugyi/Downloads/telescope_extensions.pdf
--   [ ] Explore all extensions recommended by LLMs!
--   [ ] Install https://github.com/nvim-telescope/telescope-file-browser.nvim !
--   [ ] Install https://github.com/nvim-telescope/telescope-ui-select.nvim !
--   [ ] Install extension for CodeSearch.
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
	-- telescope-fzf-native
	{
		"nvim-telescope/telescope-fzf-native.nvim",
		build = "make",
		init = function()
			require("telescope").load_extension("fzf")
		end,
	},
	-- P0: Finish setting up telescope-file-browser!
	-- telescope-file-browser
	{
		"nvim-telescope/telescope-file-browser.nvim",
		dependencies = { "nvim-telescope/telescope.nvim", "nvim-lua/plenary.nvim" },
	},
	-- telescope-all-recent
	{
		"prochri/telescope-all-recent.nvim",
		dependencies = {
			"nvim-telescope/telescope.nvim",
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
	-- telescope-luasnip
	{
		"benfowler/telescope-luasnip.nvim",
		dependencies = {
			"nvim-telescope/telescope.nvim",
			"L3MON4D3/LuaSnip",
		},
		init = function()
			vim.keymap.set("n", "<leader>ts", "<cmd>Telescope luasnip<cr>", { desc = "Telescope luasnip" })
		end,
	},
}
