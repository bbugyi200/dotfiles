--- CodeCompanion /clfiles slash command.
---
--- Allows users to seleect files that are output from the `clfiles` command
--- and add them to the chat context.

return {
	keymaps = {
		modes = { i = "<c-g>cl", n = "gcl" },
	},
	callback = function(chat)
		-- Prompt user for clfiles query
		vim.ui.input({
			prompt = "Clfiles query: ",
			default = "",
		}, function(query)
			if not query or query == "" then
				vim.notify("No query provided", vim.log.levels.WARN)
				return
			end

			-- Run clfiles command with the query
			local cmd = { "clfiles", query }
			---@diagnostic disable-next-line: missing-fields
			local job = require("plenary.job"):new({
				command = cmd[1],
				args = { cmd[2] },
				on_exit = function(j, return_val)
					if return_val == 0 then
						local stdout = j:result()
						local stderr = j:stderr_result()
						local stderr_content = table.concat(stderr, "\n")

						if stderr_content and stderr_content ~= "" then
							vim.notify("STDERR: " .. stderr_content, vim.log.levels.WARN)
						end

						-- Parse file paths from stdout
						local file_paths = {}
						for _, line in ipairs(stdout) do
							local trimmed = vim.trim(line)
							if trimmed ~= "" and vim.fn.filereadable(trimmed) == 1 then
								table.insert(file_paths, trimmed)
							end
						end

						if #file_paths == 0 then
							vim.schedule(function()
								vim.notify("No readable files found for query: " .. query, vim.log.levels.WARN)
							end)
							return
						end

						-- Schedule the file selection for the main event loop
						vim.schedule(function()
							-- Use telescope for file selection with multi-select capability
							local pickers = require("telescope.pickers")
							local finders = require("telescope.finders")
							local conf = require("telescope.config").values
							local actions = require("telescope.actions")
							local action_state = require("telescope.actions.state")

							pickers
								.new({}, {
									prompt_title = string.format("Clfiles Results (%d files)", #file_paths),
									finder = finders.new_table({
										results = file_paths,
										entry_maker = function(entry)
											return {
												value = entry,
												display = vim.fn.fnamemodify(entry, ":."),
												ordinal = vim.fn.fnamemodify(entry, ":."),
												path = entry,
											}
										end,
									}),
									sorter = conf.generic_sorter({}),
									attach_mappings = function(prompt_bufnr, map)
										actions.select_default:replace(function()
											local picker = action_state.get_current_picker(prompt_bufnr)
											local multi_selection = picker:get_multi_selection()
											local paths = {}

											-- Handle multi-selection first
											if #multi_selection > 0 then
												for _, entry in ipairs(multi_selection) do
													table.insert(paths, entry.value)
												end
											else
												-- Single selection fallback
												local selection = action_state.get_selected_entry()
												if selection then
													table.insert(paths, selection.value)
												end
											end

											actions.close(prompt_bufnr)

											if #paths > 0 then
												-- Add each file to the chat context
												for _, path in ipairs(paths) do
													local content = table.concat(vim.fn.readfile(path), "\n")
													chat:add_reference({
														role = "user",
														content = string.format(
															"File: %s\n\n```%s\n%s\n```",
															vim.fn.fnamemodify(path, ":."),
															vim.fn.fnamemodify(path, ":e"),
															content
														),
													}, "file", path)
												end
												vim.notify(string.format("Added %d files to chat context", #paths))
											else
												vim.notify("No files selected", vim.log.levels.WARN)
											end
										end)

										-- Allow multi-select with Tab
										map("i", "<Tab>", actions.toggle_selection + actions.move_selection_worse)
										map("n", "<Tab>", actions.toggle_selection + actions.move_selection_worse)
										map("i", "<S-Tab>", actions.toggle_selection + actions.move_selection_better)
										map("n", "<S-Tab>", actions.toggle_selection + actions.move_selection_better)

										return true
									end,
								})
								:find()
						end)
					else
						local stderr = j:stderr_result()
						local error_msg = table.concat(stderr, "\n")
						vim.schedule(function()
							vim.notify("clfiles command failed: " .. error_msg, vim.log.levels.ERROR)
						end)
					end
				end,
			})

			job:start()
		end)
	end,
	description = "Query files using clfiles command and add selected files to context",
	opts = {
		contains_code = true,
	},
}
