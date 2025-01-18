-- P0: Install Telescope extensions!
--   [X] Install prochri/telescope-all-recent.nvim to sort 'buffers' by most recent!
--   [X] Use ,t<L> maps with Telescope builtins and extensions!
--   [X] Install https://github.com/nvim-telescope/telescope-ui-select.nvim !
--   [ ] Install https://github.com/AckslD/nvim-neoclip.lua !
--   [ ] Explore all extensions highlighted in file:///Users/bbugyi/Downloads/telescope_extensions.pdf
--   [ ] Explore all extensions recommended by LLMs!
--   [ ] Install extension for CodeSearch.
-- P1: Fix ,ta to goto autocommand definitions (nvim -V1 seems to work)!
-- P1: Add ,tS snippet to edit SNIPPETs!
-- P1: Add ,tK snippet to edit KEYMAPs!
return {
	{
		"nvim-telescope/telescope.nvim",
		branch = "0.1.x",
		dependencies = { "nvim-lua/plenary.nvim" },
		config = function()
			local lga_actions = require("telescope-live-grep-args.actions")
			local actions = require("telescope.actions")

			--- Send Telescope results to Trouble!
			---
			---@param prompt_bufnr number The prompt buffer number.
			local function send_to_trouble(prompt_bufnr)
				actions.send_to_qflist(prompt_bufnr)
				vim.cmd("cclose | Trouble qflist")
			end

			require("telescope").setup({
				defaults = {
					sorting_strategy = "ascending",
					mappings = {
						i = {
							["<c-q>"] = send_to_trouble,
						},
						n = {
							["<c-q>"] = send_to_trouble,
						},
					},
				},
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

			-- Command-line abbreviation to make it easier to use Telescope.
			vim.cmd("cnoreabbrev ;t Telescope")

			-- KEYMAP: <c-space>
			vim.keymap.set("n", "<c-space>", builtin.resume, { desc = "Telescope resume" })
			-- KEYMAP: <leader>ta
			vim.keymap.set("n", "<leader>ta", "<cmd>Telescope autocommands<cr>", { desc = "Telescope autocommands" })
			-- KEYMAP: <leader>tb
			vim.keymap.set("n", "<leader>tb", builtin.buffers, { desc = "Telescope buffers" })
			-- KEYMAP: <leader>tc
			vim.keymap.set(
				"n",
				"<leader>tc",
				"<cmd>Telescope command_history<cr>",
				{ desc = "Telescope command_history" }
			)
			-- KEYMAP: <leader>tC
			vim.keymap.set("n", "<leader>tC", "<cmd>Telescope commands<cr>", { desc = "Telescope commands" })
			-- KEYMAP: <leader>tf
			vim.keymap.set("n", "<leader>tf", builtin.find_files, { desc = "Telescope find files" })
			-- KEYMAP: <leader>th
			vim.keymap.set("n", "<leader>th", builtin.help_tags, { desc = "Telescope help tags" })
			-- KEYMAP: <leader>tk
			vim.keymap.set("n", "<leader>tk", "<cmd>Telescope keymaps<cr>", { desc = "Telescope keymaps" })
			-- KEYMAP: <leader>tm
			vim.keymap.set("n", "<leader>tm", "<cmd>Telescope marks<cr>", { desc = "Telescope marks" })
			-- KEYMAP: <leader>to
			vim.keymap.set("n", "<leader>to", "<cmd>Telescope treesitter<cr>", { desc = "Telescope treesitter" })
			-- KEYMAP: <leader>tr
			vim.keymap.set("n", "<leader>tr", "<cmd>Telescope registers<cr>", { desc = "Telescope registers" })
			-- KEYMAP: <leader>tsh
			vim.keymap.set(
				"n",
				"<leader>tsh",
				"<cmd>Telescope search_history<cr>",
				{ desc = "Telescope search_history" }
			)
			-- KEYMAP: <leader>tt
			vim.keymap.set("n", "<leader>tt", "<cmd>Telescope<cr>", { desc = "Telescope" })
		end,
	},
	-- smart-open
	{
		"danielfalk/smart-open.nvim",
		branch = "0.2.x",
		dependencies = {
			"kkharji/sqlite.lua",
		},
		init = function()
			require("telescope").load_extension("smart_open")

			-- KEYMAP: <space>
			vim.keymap.set("n", "<space>", "<cmd>Telescope smart_open<cr>", { desc = "Telescope smart_open" })
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
	-- telescope-heading
	{
		"crispgm/telescope-heading.nvim",
		init = function()
			require("telescope").load_extension("heading")
			-- KEYMAP: <leader>tH
			vim.keymap.set("n", "<leader>tH", "<cmd>Telescope heading<cr>", { desc = "Telescope heading" })
		end,
	},
	-- telescope-live-grep-args
	{
		"nvim-telescope/telescope-live-grep-args.nvim",
		init = function()
			-- KEYMAP: <leader>tg
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
			-- KEYMAP: <leader>tsn
			vim.keymap.set("n", "<leader>tsn", "<cmd>Telescope luasnip<cr>", { desc = "Telescope luasnip" })
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
