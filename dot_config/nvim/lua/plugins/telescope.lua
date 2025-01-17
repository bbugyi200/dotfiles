-- P0: Install Telescope extensions!
--   [X] Install prochri/telescope-all-recent.nvim to sort 'buffers' by most recent!
--   [X] Use ,t<L> maps with Telescope builtins and extensions!
--   [X] Install https://github.com/nvim-telescope/telescope-ui-select.nvim !
--   [ ] Install https://github.com/AckslD/nvim-neoclip.lua !
--   [ ] Explore all extensions highlighted in file:///Users/bbugyi/Downloads/telescope_extensions.pdf
--   [ ] Explore all extensions recommended by LLMs!
--   [ ] Install extension for CodeSearch.
return {
	{
		"nvim-telescope/telescope.nvim",
		branch = "0.1.x",
		dependencies = { "nvim-lua/plenary.nvim" },
		config = function()
			local lga_actions = require("telescope-live-grep-args.actions")

			require("telescope").setup({
				defaults = { sorting_strategy = "ascending" },
				extensions = {
					heading = {
						picker_opts = {
							layout_config = { width = 0.8, preview_width = 0.5 },
							layout_strategy = "horizontal",
						},
						treesitter = true,
					},
					live_grep_args = {
						auto_quoting = true, -- enable/disable auto-quoting
						mappings = { -- extend mappings
							i = {
								["<C-k>"] = lga_actions.quote_prompt(),
								["<C-g>"] = lga_actions.quote_prompt({ postfix = " -g " }),
								["<C-t>"] = lga_actions.quote_prompt({ postfix = " -t " }),
							},
						},
					},
					["ui-select"] = { require("telescope.themes").get_dropdown({}) },
				},
			})
		end,
		init = function()
			local builtin = require("telescope.builtin")

			-- NOTE: Maps that should support telescope-all-recent neede to use a
			--   function for {rhs}.
			--
			-- KEYMAP: <space>
			vim.keymap.set("n", "<space>", function()
				builtin.buffers()
			end, { desc = "Telescope buffers" })
			-- KEYMAP: <leader>ta
			vim.keymap.set("n", "<leader>ta", "<cmd>Telescope autocmds<cr>", { desc = "Telescope autocmds" })
			-- KEYMAP: <leader>tb
			vim.keymap.set("n", "<leader>tb", function()
				builtin.buffers()
			end, { desc = "Telescope buffers" })
			-- KEYMAP: <leader>tf
			vim.keymap.set("n", "<leader>tf", function()
				builtin.find_files()
			end, { desc = "Telescope find files" })
			-- KEYMAP: <leader>tH
			vim.keymap.set("n", "<leader>tH", function()
				builtin.help_tags()
			end, { desc = "Telescope help tags" })
			-- KEYMAP: <leader>tk
			vim.keymap.set("n", "<leader>tk", "<cmd>Telescope keymaps<cr>", { desc = "Telescope keymaps" })
			-- KEYMAP: <leader>tr
			vim.keymap.set("n", "<leader>tr", "<cmd>Telescope resume<cr>", { desc = "Telescope resume" })
			-- KEYMAP: <leader>tt
			vim.keymap.set("n", "<leader>tt", "<cmd>Telescope<cr>", { desc = "Telescope" })
		end,
	},
	-- telescope-all-recent
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
				},
			},
		},
	},
	-- telescope-fzf-native
	{
		"nvim-telescope/telescope-fzf-native.nvim",
		build = "make",
		init = function()
			require("telescope").load_extension("fzf")
		end,
	},
	-- telescope-heading
	{
		"crispgm/telescope-heading.nvim",
		init = function()
			require("telescope").load_extension("heading")
			vim.keymap.set("n", "<leader>th", "<cmd>Telescope heading<cr>", { desc = "Telescope heading" })
		end,
	},
	-- telescope-live-grep-args
	{
		"nvim-telescope/telescope-live-grep-args.nvim",
		init = function()
			vim.keymap.set(
				"n",
				"<leader>tg",
				":lua require('telescope').extensions.live_grep_args.live_grep_args()<CR>",
				{ desc = "Telescope live_grep_args" }
			)
			require("telescope").load_extension("live_grep_args")
		end,
	},
	-- telescope-luasnip
	{
		"benfowler/telescope-luasnip.nvim",
		dependencies = {
			"L3MON4D3/LuaSnip",
		},
		init = function()
			vim.keymap.set("n", "<leader>ts", "<cmd>Telescope luasnip<cr>", { desc = "Telescope luasnip" })
			require("telescope").load_extension("luasnip")
		end,
	},
	-- telescope-ui-select
	{
		"nvim-telescope/telescope-ui-select.nvim",
		init = function()
			require("telescope").load_extension("ui-select")
		end,
	},
}
