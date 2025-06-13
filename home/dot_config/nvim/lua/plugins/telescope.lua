--- Find, Filter, Preview, Pick... Gaze deeply into unknown regions using the power of the moon.
--
-- P1: Install Telescope extension(s) for lazy.nvim:
--   [ ] Install https://github.com/tsakirist/telescope-lazy.nvim ?!
--   [ ] Install https://github.com/polirritmico/telescope-lazy-plugins.nvim ?!
-- P1: Install https://github.com/piersolenski/telescope-import.nvim !
-- P1: Add Telescope keymaps to edit parts of my configs!:
--     (Use https://github.com/adoyle-h/telescope-extension-maker.nvim for this?!)
--   [ ] ,tla keymap to edit AUTOCMDs!
--   [ ] ,tlk keymap to edit KEYMAPs!
--   [ ] ,tll keymap to edit all types of these comments!
--   [ ] ,tlo keymap to edit OPTIONs!
--   [ ] ,tlp keymap to edit PLUGINs!
--   [ ] ,tls keymap to edit SNIPPETs!
-- P2: Explore all extensions recommended by LLMs!
-- P2: Install https://github.com/jvgrootveld/telescope-zoxide !
-- P2: Install extension for CodeSearch.
-- P2: Install https://github.com/debugloop/telescope-undo.nvim !
-- P3: Fix ,ta to goto autocommand definitions (nvim -V1 seems to work)!
-- P3: Install https://github.com/jmbuhr/telescope-zotero.nvim !
--       (watch https://www.youtube.com/watch?v=_o5SkTW67do)

local bb = require("bb_utils")

local telescope_plugin_name = "nvim-telescope/telescope.nvim"

--- Wrapper for http://go/telescope-codesearch plugin.
---
---@return table<string, any> # Configuration or empty table (if not on google machine).
local function maybe_goog_telescope_plugins()
	if bb.is_goog_machine() then
		return {
			-- PLUGIN: http://go/telescope-codesearch
			{
				"vintharas/telescope-codesearch.nvim",
				url = "sso://user/vintharas/telescope-codesearch.nvim",
				dependencies = { telescope_plugin_name },
				opts = {},
				init = function()
					-- KEYMAP: <leader>tcs
					vim.keymap.set(
						"n",
						"<leader>tcs",
						"<cmd>Telescope codesearch find_query<cr>",
						{ desc = "Telescope codesearch find_query" }
					)
				end,
			},
			-- PLUGIN: http://go/telescope-fig
			{
				url = "sso://user/tylersaunders/telescope-fig.nvim",
				dependencies = { telescope_plugin_name, "nvim-lua/plenary.nvim" },
				opts = {},
				init = function()
					-- KEYMAP GROUP: <leader>tf
					vim.keymap.set("n", "<leader>tf", "<nop>", { desc = "Telescope fig" })
					-- KEYMAP: <leader>tfs
					vim.keymap.set(
						"n",
						"<leader>tfs",
						"<cmd>Telescope fig status<cr>",
						{ desc = "Telescope fig status" }
					)
					-- KEYMAP: <leader>tfx
					vim.keymap.set("n", "<leader>tfx", "<cmd>Telescope fig xl<cr>", { desc = "Telescope fig xl" })
				end,
			},
		}
	else
		return {}
	end
end

return {
	-- PLUGIN: http://github.com/nvim-telescope/telescope.nvim
	{
		telescope_plugin_name,
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
							["<c-o>"] = function(prompt_bufnr)
								require("telescope.actions").select_default(prompt_bufnr)
								require("telescope.builtin").resume()
							end,
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
			local pickers = require("telescope.pickers")
			local finders = require("telescope.finders")
			local conf = require("telescope.config").values

			-- KEYMAP: t   (:t --> :Telescope)
			vim.cmd([[
        cnoreabbrev t <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Telescope" : "t"<CR>
      ]])

			-- KEYMAP GROUP: <leader>t
			vim.keymap.set("n", "<leader>t", "<nop>", { desc = "telescope.nvim" })
			-- KEYMAP: <c-space>
			vim.keymap.set("n", "<c-space>", builtin.resume, { desc = "Telescope resume" })
			-- KEYMAP: <leader>tau
			vim.keymap.set("n", "<leader>tau", "<cmd>Telescope autocommands<cr>", {
				desc = "Telescope autocommands",
			})
			-- KEYMAP: <leader>tb
			vim.keymap.set("n", "<leader>tb", builtin.buffers, { desc = "Telescope buffers" })
			-- KEYMAP: <leader>tch
			vim.keymap.set(
				"n",
				"<leader>tch",
				"<cmd>Telescope command_history<cr>",
				{ desc = "Telescope command_history" }
			)
			-- KEYMAP: <leader>tcm
			vim.keymap.set("n", "<leader>tcm", "<cmd>Telescope commands<cr>", { desc = "Telescope commands" })
			-- KEYMAP: <leader>tF
			vim.keymap.set("n", "<leader>tF", builtin.find_files, { desc = "Telescope find files" })
			-- KEYMAP: <leader>tH
			vim.keymap.set("n", "<leader>tH", builtin.help_tags, { desc = "Telescope help tags" })
			-- KEYMAP: <leader>tj
			vim.keymap.set("n", "<leader>tj", "<cmd>Telescope jumplist<cr>", { desc = "Telescope jumplist" })
			-- KEYMAP: <leader>tk
			vim.keymap.set("n", "<leader>tk", "<cmd>Telescope keymaps<cr>", { desc = "Telescope keymaps" })
			-- KEYMAP: <leader>tL
			vim.keymap.set("n", "<leader>tL", "<cmd>Telescope loclist<cr>", { desc = "Telescope loclist" })
			-- KEYMAP: <leader>tm
			vim.keymap.set("n", "<leader>tm", "<cmd>Telescope marks<cr>", { desc = "Telescope marks" })
			-- KEYMAP: <leader>tre
			vim.keymap.set("n", "<leader>tre", "<cmd>Telescope treesitter<cr>", { desc = "Telescope treesitter" })
			-- KEYMAP: <leader>trg
			vim.keymap.set("n", "<leader>trg", "<cmd>Telescope registers<cr>", { desc = "Telescope registers" })
			-- KEYMAP: <leader>tsh
			vim.keymap.set(
				"n",
				"<leader>tsh",
				"<cmd>Telescope search_history<cr>",
				{ desc = "Telescope search_history" }
			)
			-- KEYMAP: <leader>tT
			vim.keymap.set("n", "<leader>tT", "<cmd>Telescope<cr>", { desc = "Telescope builtin" })
			-- KEYMAP: <leader>tqf
			vim.keymap.set("n", "<leader>tqf", "<cmd>Telescope quickfix<cr>", { desc = "Telescope quickfix" })
			-- KEYMAP: <leader>tbc
			vim.keymap.set("n", "<leader>tbc", function()
				-- Execute branch_changes script and capture output
				local handle = io.popen("branch_changes 2>/dev/null")
				if not handle then
					vim.notify("Failed to execute branch_changes script", vim.log.levels.ERROR)
					return
				end

				local output = handle:read("*a")
				handle:close()

				-- Split output into lines and filter out empty lines
				local files = {}
				for line in output:gmatch("[^\r\n]+") do
					if line:match("%S") then -- Only add non-empty lines
						table.insert(files, line)
					end
				end

				if #files == 0 then
					vim.notify("No files found from branch_changes script", vim.log.levels.WARN)
					return
				end

				pickers
					.new({}, {
						prompt_title = "Branch Changes",
						finder = finders.new_table({
							results = files,
						}),
						sorter = conf.generic_sorter({}),
						previewer = conf.file_previewer({}),
					})
					:find()
			end, { desc = "Telescope branch changes" })
		end,
	},
	-- PLUGIN: http://github.com/AckslD/nvim-neoclip.lua
	{
		"AckslD/nvim-neoclip.lua",
		dependencies = {
			{
				telescope_plugin_name,
				{ "kkharji/sqlite.lua", module = "sqlite" },
			},
		},
		opts = { enable_persistent_history = true },
		init = function()
			-- KEYMAP: <leader>tn
			vim.keymap.set("n", "<leader>tn", "<cmd>Telescope neoclip plus<cr>", { desc = "Telescope neoclip plus" })
			-- KEYMAP: <leader>tqq
			vim.keymap.set("n", "<leader>tqq", "<cmd>Telescope macroscope<cr>", { desc = "Telescope macroscope" })
		end,
	},
	-- PLUGIN: http://github.com/danielfalk/smart-open.nvim
	{
		"danielfalk/smart-open.nvim",
		branch = "0.2.x",
		dependencies = {
			telescope_plugin_name,
			"kkharji/sqlite.lua",
		},
		init = function()
			require("telescope").load_extension("smart_open")

			if bb.is_goog_machine() then
				-- KEYMAP: <space>
				vim.keymap.set("n", "<space>", "<cmd>Telescope buffers<cr>", { desc = "Telescope buffers" })
				-- KEYMAP: <leader><space>
				vim.keymap.set(
					"n",
					"<leader><space>",
					"<cmd>Telescope smart_open<cr>",
					{ desc = "Telescope smart_open" }
				)
			else
				-- KEYMAP: <space>
				vim.keymap.set("n", "<space>", "<cmd>Telescope smart_open<cr>", { desc = "Telescope smart_open" })
			end
		end,
	},
	-- PLUGIN: http://github.com/nvim-telescope/telescope-fzf-native.nvim
	{
		"nvim-telescope/telescope-fzf-native.nvim",
		build = "make",
		dependencies = {
			{ telescope_plugin_name },
		},
		init = function()
			require("telescope").load_extension("fzf")
		end,
	},
	-- PLUGIN: http://github.com/crispgm/telescope-heading.nvim
	{
		"crispgm/telescope-heading.nvim",
		dependencies = {
			{ telescope_plugin_name },
		},
		init = function()
			require("telescope").load_extension("heading")
			-- AUTOCMD: Add 'H' keymap to run ':Telescope heading' for vimdoc / markdown / rst files.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "markdown", "help", "rst" },
				callback = function()
					-- KEYMAP: H
					vim.keymap.set("n", "H", "<cmd>Telescope heading<cr>", { desc = "Telescope heading" })
				end,
			})
		end,
	},
	-- PLUGIN: http://github.com/nvim-telescope/telescope-live-grep-args.nvim
	{
		"nvim-telescope/telescope-live-grep-args.nvim",
		dependencies = {
			{ telescope_plugin_name },
		},
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
	-- PLUGIN: http://github.com/benfowler/telescope-luasnip.nvim
	{
		"benfowler/telescope-luasnip.nvim",
		dependencies = {
			telescope_plugin_name,
			"L3MON4D3/LuaSnip",
		},
		init = function()
			-- KEYMAP: <leader>tsn
			vim.keymap.set("n", "<leader>tsn", "<cmd>Telescope luasnip<cr>", { desc = "Telescope luasnip" })
			require("telescope").load_extension("luasnip")
		end,
	},
	-- PLUGIN: http://github.com/nvim-telescope/telescope-ui-select.nvim
	{
		"nvim-telescope/telescope-ui-select.nvim",
		dependencies = {
			{ telescope_plugin_name },
		},
		init = function()
			require("telescope").load_extension("ui-select")
		end,
	},
	-- PLUGIN: http://go/telescope-codesearch
	maybe_goog_telescope_plugins(),
}
