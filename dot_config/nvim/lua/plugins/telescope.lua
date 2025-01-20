-- P0: Install Telescope extensions!
--   [X] Install prochri/telescope-all-recent.nvim to sort 'buffers' by most recent!
--   [X] Use ,t<L> maps with Telescope builtins and extensions!
--   [X] Install https://github.com/nvim-telescope/telescope-ui-select.nvim !
--   [X] Install https://github.com/AckslD/nvim-neoclip.lua !
--   [X] Install https://github.com/arjunmahishi/flow.nvim !
--   [X] Explore all extensions highlighted in file:///Users/bbugyi/Downloads/telescope_extensions.pdf
--   [ ] Install https://github.com/otavioschwanck/telescope-alternate.nvim !
--   [ ] Install https://github.com/debugloop/telescope-undo.nvim !
--   [ ] Install https://github.com/MaximilianLloyd/adjacent.nvim !
--   [ ] Install https://github.com/piersolenski/telescope-import.nvim !
--   [ ] Install https://github.com/jmbuhr/telescope-zotero.nvim !
--       (watch https://www.youtube.com/watch?v=_o5SkTW67do)
--   [ ] Install https://github.com/jvgrootveld/telescope-zoxide !
--   [ ] Install https://github.com/tsakirist/telescope-lazy.nvim !
--   [ ] Install https://github.com/polirritmico/telescope-lazy-plugins.nvim ?
--   [ ] Explore all extensions recommended by LLMs!
--   [ ] Install extension for CodeSearch.
-- P1: Add Telescope keymaps to edit parts of my configs!:
--     (Use https://github.com/adoyle-h/telescope-extension-maker.nvim for this?!)
--   [ ] ,tla keymap to edit AUTOCMDs!
--   [ ] ,tls keymap to edit SNIPPETs!
--   [ ] ,tlk keymap to edit KEYMAPs!
--   [ ] ,tll keymap to edit all types of these comments!
--   [ ] ,tlp keymap to edit PLUGINs!
-- P3: Fix ,ta to goto autocommand definitions (nvim -V1 seems to work)!
return {
	-- PLUGIN: http://github.com/nvim-telescope/telescope.nvim
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
							["<c-x>"] = send_to_trouble,
						},
						n = {
							["<c-x>"] = send_to_trouble,
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

			-- KEYMAP(N): <c-space>
			vim.keymap.set("n", "<c-space>", builtin.resume, { desc = "Telescope resume" })
			-- KEYMAP(N): <leader>ta
			vim.keymap.set("n", "<leader>ta", "<cmd>Telescope autocommands<cr>", { desc = "Telescope autocommands" })
			-- KEYMAP(N): <leader>tb
			vim.keymap.set("n", "<leader>tb", builtin.buffers, { desc = "Telescope buffers" })
			-- KEYMAP(N): <leader>tc
			vim.keymap.set(
				"n",
				"<leader>tc",
				"<cmd>Telescope command_history<cr>",
				{ desc = "Telescope command_history" }
			)
			-- KEYMAP(N): <leader>tC
			vim.keymap.set("n", "<leader>tC", "<cmd>Telescope commands<cr>", { desc = "Telescope commands" })
			-- KEYMAP(N): <leader>tF
			vim.keymap.set("n", "<leader>tF", builtin.find_files, { desc = "Telescope find files" })
			-- KEYMAP(N): <leader>th
			vim.keymap.set("n", "<leader>th", builtin.help_tags, { desc = "Telescope help tags" })
			-- KEYMAP(N): <leader>tj
			vim.keymap.set("n", "<leader>tj", "<cmd>Telescope jumplist<cr>", { desc = "Telescope jumplist" })
			-- KEYMAP(N): <leader>tk
			vim.keymap.set("n", "<leader>tk", "<cmd>Telescope keymaps<cr>", { desc = "Telescope keymaps" })
			-- KEYMAP(N): <leader>tm
			vim.keymap.set("n", "<leader>tm", "<cmd>Telescope marks<cr>", { desc = "Telescope marks" })
			-- KEYMAP(N): <leader>to
			vim.keymap.set("n", "<leader>to", "<cmd>Telescope treesitter<cr>", { desc = "Telescope treesitter" })
			-- KEYMAP(N): <leader>tr
			vim.keymap.set("n", "<leader>tr", "<cmd>Telescope registers<cr>", { desc = "Telescope registers" })
			-- KEYMAP(N): <leader>tsh
			vim.keymap.set(
				"n",
				"<leader>tsh",
				"<cmd>Telescope search_history<cr>",
				{ desc = "Telescope search_history" }
			)
			-- KEYMAP(N): <leader>tt
			vim.keymap.set("n", "<leader>tt", "<cmd>Telescope<cr>", { desc = "Telescope" })
			-- KEYMAP(N): <leader>tqf
			vim.keymap.set("n", "<leader>tqf", "<cmd>Telescope quickfix<cr>", { desc = "Telescope quickfix" })
		end,
	},
	-- PLUGIN: https://github.com/arjunmahishi/flow.nvim
	{
		"arjunmahishi/flow.nvim",
		opts = {
			custom_cmd_dir = os.getenv("HOME") .. "/.local/share/chezmoi/dot_config/nvim/flow_cmds",
			filetype_cmd_map = { zorg = "bash -c '%s'" },
		},
		dependencies = {
			{ "nvim-telescope/telescope.nvim" },
		},
		init = function()
			require("telescope").load_extension("flow")

			-- KEYMAP(N): <leader>tf
			vim.keymap.set("n", "<leader>tf", "<cmd>Telescope flow<cr>", { desc = "Telescope flow" })
			-- KEYMAP(X): <leader>f
			vim.keymap.set(
				"x",
				"<leader>f",
				"<cmd>FlowRunSelected<cr>",
				{ desc = "Run visually selected code using Flow." }
			)
			-- KEYMAP(N): <leader>fo
			vim.keymap.set("n", "<leader>fo", "<cmd>FlowLastOutput<cr>", { desc = "View output of last Flow command." })
			-- KEYMAP(N): <leader>ff
			vim.keymap.set("n", "<leader>ff", "<cmd>FlowRunLastCmd<cr>", { desc = "Run last Flow command." })
			-- KEYMAP(N): <leader>fr
			vim.keymap.set("n", "<leader>fr", "<cmd>FlowRunFile<cr>", { desc = "Run code in file using Flow." })
		end,
	},
	-- PLUGIN: http://github.com/AckslD/nvim-neoclip.lua
	{
		"AckslD/nvim-neoclip.lua",
		dependencies = {
			{
				"nvim-telescope/telescope.nvim",
				{ "kkharji/sqlite.lua", module = "sqlite" },
			},
		},
		opts = { enable_persistent_history = true },
		init = function()
			-- KEYMAP(N): <leader>tn
			vim.keymap.set("n", "<leader>tn", "<cmd>Telescope neoclip plus<cr>", { desc = "Telescope neoclip plus" })
			-- KEYMAP(N): <leader>tqq
			vim.keymap.set("n", "<leader>tqq", "<cmd>Telescope macroscope<cr>", { desc = "Telescope macroscope" })
		end,
	},
	-- PLUGIN: http://github.com/danielfalk/smart-open.nvim
	{
		"danielfalk/smart-open.nvim",
		branch = "0.2.x",
		dependencies = {
			"nvim-telescope/telescope.nvim",
			"kkharji/sqlite.lua",
		},
		init = function()
			require("telescope").load_extension("smart_open")

			-- KEYMAP(N): <space>
			vim.keymap.set("n", "<space>", "<cmd>Telescope smart_open<cr>", { desc = "Telescope smart_open" })
		end,
	},
	-- PLUGIN: http://github.com/nvim-telescope/telescope-fzf-native.nvim
	{
		"nvim-telescope/telescope-fzf-native.nvim",
		build = "make",
		dependencies = {
			{ "nvim-telescope/telescope.nvim" },
		},
		init = function()
			require("telescope").load_extension("fzf")
		end,
	},
	-- PLUGIN: http://github.com/crispgm/telescope-heading.nvim
	{
		"crispgm/telescope-heading.nvim",
		dependencies = {
			{ "nvim-telescope/telescope.nvim" },
		},
		init = function()
			require("telescope").load_extension("heading")
			-- Add 'H' keymap to run ':Telescope heading' for vimdoc / markdown / rst files.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "markdown", "help", "rst" },
				callback = function()
					local ftype = vim.bo.filetype
					-- KEYMAP(N): H
					vim.keymap.set(
						"n",
						"H",
						"<cmd>Telescope heading<cr>",
						{ desc = string.format("Telescope picker for %s section headings.", ftype) }
					)
				end,
			})
		end,
	},
	-- PLUGIN: http://github.com/nvim-telescope/telescope-live-grep-args.nvim
	{
		"nvim-telescope/telescope-live-grep-args.nvim",
		dependencies = {
			{ "nvim-telescope/telescope.nvim" },
		},
		init = function()
			-- KEYMAP(N): <leader>tg
			vim.keymap.set(
				"n",
				"<leader>tg",
				":lua require('telescope').extensions.live_grep_args.live_grep_args()<CR>",
				{ desc = "Telescope live_grep_args" }
			)
			require("telescope").load_extension("live_grep_args")
		end,
	},
	-- PLUGIN: http://github.com/benfowler/telescope-luasnip.nvim
	{
		"benfowler/telescope-luasnip.nvim",
		dependencies = {
			"nvim-telescope/telescope.nvim",
			"L3MON4D3/LuaSnip",
		},
		init = function()
			-- KEYMAP(N): <leader>tsn
			vim.keymap.set("n", "<leader>tsn", "<cmd>Telescope luasnip<cr>", { desc = "Telescope luasnip" })
			require("telescope").load_extension("luasnip")
		end,
	},
	-- PLUGIN: http://github.com/nvim-telescope/telescope-ui-select.nvim
	{
		"nvim-telescope/telescope-ui-select.nvim",
		dependencies = {
			{ "nvim-telescope/telescope.nvim" },
		},
		init = function()
			require("telescope").load_extension("ui-select")
		end,
	},
}
