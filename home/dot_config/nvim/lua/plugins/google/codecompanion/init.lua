local cc = require("plugins.codecompanion.common")

return vim.tbl_deep_extend("force", cc.common_plugin_config, {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		config = function()
			local goose = require("plugins.google.codecompanion.goose")
			goose.setup({
				auto_start_backend = false,
				auto_start_silent = false,
				temperature = 0.1,
				endpoint = "http://localhost:8649/predict",
				debug = vim.env.CC_GOOSE_DEBUG ~= nil,
				debug_backend = false,
			})

			require("codecompanion").setup(vim.tbl_deep_extend("force", cc.common_setup_opts, {
				adapters = {
					little_goose = goose.get_adapter("LittleGoose", "goose-v3.5-s", 8192),
					big_goose = goose.get_adapter("BigGoose", "gemini-for-google-2.5-pro", 65536),
				},
				strategies = {
					chat = {
						adapter = "big_goose",
						slash_commands = {
							xfiles = {
								callback = function(codecompanion)
									-- Check if telescope-codesearch is available
									local telescope = require("telescope")
									if not telescope.extensions.codesearch then
										vim.notify("telescope-codesearch extension not found", vim.log.levels.ERROR)
										return
									end

									-- Show a choice between find_files and find_query
									vim.ui.select({
										"Find Files (fuzzy)",
										"Find Query (codesearch syntax)",
									}, {
										prompt = "Select codesearch mode:",
									}, function(choice)
										if not choice then
											return
										end

										local picker_opts = {
											attach_mappings = function(prompt_bufnr, map)
												local actions = require("telescope.actions")
												local action_state = require("telescope.actions.state")

												-- Override the default action to add files to codecompanion context
												actions.select_default:replace(function()
													local selections = action_state.get_selected_entries(prompt_bufnr)
													local paths = {}

													-- Handle both single and multiple selections
													if #selections == 0 then
														local current = action_state.get_selected_entry()
														if current then
															table.insert(
																paths,
																current.value or current.path or current.filename
															)
														end
													else
														for _, selection in ipairs(selections) do
															table.insert(
																paths,
																selection.value or selection.path or selection.filename
															)
														end
													end

													if #paths > 0 then
														codecompanion.add_workspace_context(paths)
														vim.notify(
															string.format(
																"Added %d file(s) to CodeCompanion context",
																#paths
															),
															vim.log.levels.INFO
														)
													end
													actions.close(prompt_bufnr)
												end)

												-- Allow multi-select with Tab
												map(
													"i",
													"<Tab>",
													actions.toggle_selection + actions.move_selection_worse
												)
												map(
													"n",
													"<Tab>",
													actions.toggle_selection + actions.move_selection_worse
												)
												map(
													"i",
													"<S-Tab>",
													actions.toggle_selection + actions.move_selection_better
												)
												map(
													"n",
													"<S-Tab>",
													actions.toggle_selection + actions.move_selection_better
												)

												return true
											end,
											-- Add some useful codesearch options
											experimental = true, -- Include experimental directory
											enable_proximity = true, -- Enable proximity search
											max_num_results = 100, -- Increase max results
										}

										if choice:match("Find Files") then
											telescope.extensions.codesearch.find_files(picker_opts)
										else
											telescope.extensions.codesearch.find_query(picker_opts)
										end
									end)
								end,
								description = "Add files from codesearch to context (fuzzy or query mode)",
								opts = {
									contains_code = true,
								},
							},
						},
					},
					inline = {
						adapter = "big_goose",
					},
					cmd = {
						adapter = "big_goose",
					},
				},
			}))
		end,
		init = function()
			cc.common_init()

			-- KEYMAP: <leader>ccs
			cc.create_adapter_switch_keymap("little_goose", "big_goose")

			-- AUTOCMD: Configure 'ge' keymap to comment-paste clipboard and transform code.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "codecompanion" },
				callback = function()
					-- KEYMAP: ge
					vim.keymap.set("n", "ge", function()
						if vim.v.count > 0 then
							vim.cmd("normal! y" .. vim.v.count .. "j")
							vim.cmd("normal! " .. vim.v.count + 1 .. "jzz")
						end

						-- Navigate to previous buffer
						vim.cmd("wincmd w")

						-- Jump to bottom of buffer
						vim.cmd("normal! G")

						-- Paste clipboard contents
						vim.cmd("normal! p")

						-- Comment out the pasted content
						vim.cmd("normal gcG")

						-- Run the transform command
						vim.cmd("TransformCode Implement the edits described at the bottom of the file in comments.")
					end, { desc = "Implement clipboard CodeCompanion edits using ai.nvim.", buffer = 0 })

					-- KEYMAP: gE
					vim.keymap.set("n", "gE", function()
						vim.cmd("normal gyge")
					end, { desc = "Implement CodeCompanion edits under cursor using ai.nvim.", buffer = 0 })
				end,
			})
		end,
	},
})
