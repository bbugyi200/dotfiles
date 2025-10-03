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

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
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
			if bb.is_goog_machine() then
				-- KEYMAP: <leader>tbc
				vim.keymap.set("n", "<leader>tbc", function()
					-- Check if all commands exist
					if vim.fn.executable("branch_changes") ~= 1 then
						vim.notify("branch_changes command not found in PATH", vim.log.levels.ERROR)
						return
					end
					if vim.fn.executable("branch_chain_changes") ~= 1 then
						vim.notify("branch_chain_changes command not found in PATH", vim.log.levels.ERROR)
						return
					end
					if vim.fn.executable("branch_local_changes") ~= 1 then
						vim.notify("branch_local_changes command not found in PATH", vim.log.levels.ERROR)
						return
					end

					-- Run all three commands in parallel
					local chain_files = {}
					local branch_files = {}
					local local_files = {}
					local completed_jobs = 0
					local total_jobs = 3

					local function check_completion()
						completed_jobs = completed_jobs + 1
						if completed_jobs == total_jobs then
							-- All jobs completed, process results
							vim.schedule(function()
								-- Create file sets for easier lookup
								local branch_set = {}
								local local_set = {}

								for _, file in ipairs(branch_files) do
									branch_set[file] = true
								end

								for _, file in ipairs(local_files) do
									local_set[file] = true
								end

								-- Process all files and assign markers
								local all_files = {}
								local seen_files = {}

								-- Add all chain files with appropriate markers
								for _, file in ipairs(chain_files) do
									if vim.fn.filereadable(file) == 1 and not seen_files[file] then
										local marker
										if local_set[file] then
											marker = "[*]" -- local changes (working directory)
										elseif branch_set[file] then
											marker = "[L]" -- branch changes but not local
										else
											marker = "[G]" -- only in chain changes
										end

										table.insert(all_files, {
											path = file,
											marker = marker,
											display = marker .. " " .. file,
										})
										seen_files[file] = true
									end
								end

								if #all_files == 0 then
									vim.notify(
										"No readable files found from branch changes commands",
										vim.log.levels.WARN
									)
									return
								end

								-- Sort files by marker priority: [*] first, then [L], then [G]
								table.sort(all_files, function(a, b)
									local priority_order = { ["[*]"] = 1, ["[L]"] = 2, ["[G]"] = 3 }
									local a_priority = priority_order[a.marker] or 4
									local b_priority = priority_order[b.marker] or 4

									if a_priority == b_priority then
										-- If same priority, sort alphabetically by path
										return a.path < b.path
									end
									return a_priority < b_priority
								end)

								-- Use telescope to display files with markers
								local pickers = require("telescope.pickers")
								local finders = require("telescope.finders")
								local conf = require("telescope.config").values
								local actions = require("telescope.actions")
								local action_state = require("telescope.actions.state")

								-- Custom action to open selected files
								local function open_selected_files(prompt_bufnr)
									local picker = action_state.get_current_picker(prompt_bufnr)
									local selections = picker:get_multi_selection()

									actions.close(prompt_bufnr)

									-- If no multi-selections, use the current selection
									if vim.tbl_isempty(selections) then
										local current_selection = action_state.get_selected_entry()
										if current_selection then
											vim.cmd("edit " .. vim.fn.fnameescape(current_selection.value))
										end
									else
										-- Open all multi-selections
										for _, selection in ipairs(selections) do
											vim.cmd("edit " .. vim.fn.fnameescape(selection.value))
										end
									end
								end

								pickers
									.new({}, {
										prompt_title = string.format(
											"Branch Changes ([*]=%d local, [L]=%d branch, [G]=%d chain)",
											#local_files,
											#branch_files - #local_files,
											#chain_files - #branch_files
										),
										finder = finders.new_table({
											results = all_files,
											entry_maker = function(entry)
												return {
													value = entry.path,
													display = entry.display,
													ordinal = entry.path,
													path = entry.path,
												}
											end,
										}),
										sorter = conf.file_sorter({}),
										previewer = conf.file_previewer({}),
										attach_mappings = function(_, map)
											-- Override default select action
											actions.select_default:replace(open_selected_files)

											-- Optional: add explicit mapping
											map("i", "<C-m>", open_selected_files)
											map("n", "<CR>", open_selected_files)

											-- Allow multi-select with Tab
											map("i", "<Tab>", actions.toggle_selection + actions.move_selection_worse)
											map("n", "<Tab>", actions.toggle_selection + actions.move_selection_worse)

											return true
										end,
									})
									:find()
							end)
						end
					end

					-- Run branch_chain_changes command
					local chain_job = require("plenary.job"):new({
						command = "branch_chain_changes",
						args = {},
						on_exit = function(j, return_val)
							if return_val == 0 then
								local stdout = j:result()
								for _, line in ipairs(stdout) do
									local trimmed = vim.trim(line)
									if trimmed ~= "" then
										table.insert(chain_files, trimmed)
									end
								end
							else
								vim.schedule(function()
									vim.notify("branch_chain_changes command failed", vim.log.levels.ERROR)
								end)
							end
							check_completion()
						end,
					})

					-- Run branch_changes command
					local branch_job = require("plenary.job"):new({
						command = "branch_changes",
						args = {},
						on_exit = function(j, return_val)
							if return_val == 0 then
								local stdout = j:result()
								for _, line in ipairs(stdout) do
									local trimmed = vim.trim(line)
									if trimmed ~= "" then
										table.insert(branch_files, trimmed)
									end
								end
							else
								vim.schedule(function()
									vim.notify("branch_changes command failed", vim.log.levels.ERROR)
								end)
							end
							check_completion()
						end,
					})

					-- Run branch_local_changes command
					local local_job = require("plenary.job"):new({
						command = "branch_local_changes",
						args = {},
						on_exit = function(j, return_val)
							if return_val == 0 then
								local stdout = j:result()
								for _, line in ipairs(stdout) do
									local trimmed = vim.trim(line)
									if trimmed ~= "" then
										table.insert(local_files, trimmed)
									end
								end
							else
								vim.schedule(function()
									vim.notify("branch_local_changes command failed", vim.log.levels.ERROR)
								end)
							end
							check_completion()
						end,
					})

					-- Start all jobs
					chain_job:start()
					branch_job:start()
					local_job:start()
				end, { desc = "Telescope branch_chain_changes with markers" })
				-- KEYMAP: <leader>tbC
				vim.keymap.set("n", "<leader>tbC", function()
					bb.telescope_command_files("branch_changes", {
						prompt_title = "Branch Changes",
					})
				end, { desc = "Telescope branch_changes" })
				-- KEYMAP: <leader>tbu
				vim.keymap.set("n", "<leader>tbu", builtin.buffers, { desc = "Telescope buffers" })
			else
				-- KEYMAP: <leader>tb
				vim.keymap.set("n", "<leader>tb", builtin.buffers, { desc = "Telescope buffers" })
			end
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
