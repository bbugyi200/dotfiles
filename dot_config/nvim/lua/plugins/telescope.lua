-- P0: Install Telescope extensions!
--   [X] Install prochri/telescope-all-recent.nvim to sort 'buffers' by most recent!
--   [X] Use ,t<L> maps with Telescope builtins and extensions!
--   [ ] Install https://github.com/nvim-telescope/telescope-ui-select.nvim !
--   [ ] Explore all extensions highlighted in file:///Users/bbugyi/Downloads/telescope_extensions.pdf
--   [ ] Explore all extensions recommended by LLMs!
--   [ ] Install extension for CodeSearch.
-- P0: Finish setting up https://github.com/nvim-telescope/telescope-file-browser.nvim !
--   [ ] Add \n map to open file_browser with the path of the current buffer!
--   [ ] Flex file move..
--   [ ] Flex filename copy.
--   [ ] Flex file/dir creation.
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
	-- telescope-file-browser
	{
		"nvim-telescope/telescope-file-browser.nvim",
		dependencies = { "nvim-telescope/telescope.nvim", "nvim-lua/plenary.nvim" },
		init = function()
			vim.keymap.set("n", "<leader>tn", ":Telescope file_browser<CR>")

			-- open file_browser with the path of the current buffer
			vim.keymap.set("n", "<leader>tN", ":Telescope file_browser path=%:p:h select_buffer=true<CR>")
		end,
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
