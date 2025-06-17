return {
	clfiles = {
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
				local cmd = { vim.env.HOME .. "/bin/clfiles", query }
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
								-- Use a simple approach with vim.ui.select for multi-selection
								local selected_files = {}
								local function select_next_file(remaining_files, index)
									if index > #remaining_files then
										-- Done selecting, add files to chat
										if #selected_files > 0 then
											for _, file_path in ipairs(selected_files) do
												local content = table.concat(vim.fn.readfile(file_path), "\n")
												chat:add_reference({
													role = "user",
													content = string.format(
														"File: %s\n\n```%s\n%s\n```",
														vim.fn.fnamemodify(file_path, ":."),
														vim.fn.fnamemodify(file_path, ":e"),
														content
													),
												}, "file", file_path)
											end
											vim.notify(string.format("Added %d files to chat context", #selected_files))
										else
											vim.notify("No files selected", vim.log.levels.WARN)
										end
										return
									end

									local current_file = remaining_files[index]
									local display_name = vim.fn.fnamemodify(current_file, ":.")
									local choices = {
										"Add " .. display_name,
										"Skip " .. display_name,
										"Add remaining " .. (#remaining_files - index + 1) .. " files",
										"Done selecting",
									}

									vim.ui.select(choices, {
										prompt = string.format("File %d/%d: %s", index, #remaining_files, display_name),
									}, function(choice)
										if not choice then
											return -- User cancelled
										end

										if choice:match("^Add remaining") then
											-- Add all remaining files
											for i = index, #remaining_files do
												table.insert(selected_files, remaining_files[i])
											end
											select_next_file(remaining_files, #remaining_files + 1)
										elseif choice:match("^Add ") then
											table.insert(selected_files, current_file)
											select_next_file(remaining_files, index + 1)
										elseif choice:match("^Skip ") then
											select_next_file(remaining_files, index + 1)
										elseif choice == "Done selecting" then
											select_next_file(remaining_files, #remaining_files + 1)
										end
									end)
								end

								select_next_file(file_paths, 1)
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
	},
	cs = {
		keymaps = {
			modes = { i = "<c-g>cs", n = "gcs" },
		},
		callback = function(chat)
			-- Check if telescope-codesearch is available
			local telescope = require("telescope")
			if not telescope.extensions.codesearch then
				vim.notify("telescope-codesearch extension not found", vim.log.levels.ERROR)
				return
			end
			local picker_opts = {
				attach_mappings = function(prompt_bufnr, map)
					local actions = require("telescope.actions")
					local action_state = require("telescope.actions.state")

					actions.select_default:replace(function()
						local picker = action_state.get_current_picker(prompt_bufnr)
						local multi_selection = picker:get_multi_selection()
						local paths = {}

						-- Handle multi-selection first
						if #multi_selection > 0 then
							for _, entry in ipairs(multi_selection) do
								local path = entry.value or entry.path or entry.filename
								if path then
									table.insert(paths, path)
								end
							end
						else
							-- Single selection fallback
							local selection = action_state.get_selected_entry()
							if selection then
								local path = selection.value or selection.path or selection.filename
								if path then
									table.insert(paths, path)
								end
							end
						end

						actions.close(prompt_bufnr)

						if #paths > 0 then
							-- Add each file to the chat context
							for _, path in ipairs(paths) do
								if vim.fn.filereadable(path) == 1 then
									-- Read the file content
									local content = table.concat(vim.fn.readfile(path), "\n")

									-- Add the file as a reference to the chat
									chat:add_reference({
										role = "user",
										content = string.format(
											"File: %s\n\n```%s\n%s\n```",
											vim.fn.fnamemodify(path, ":."),
											vim.fn.fnamemodify(path, ":e"),
											content
										),
									}, "file", path)

									vim.notify("Added " .. vim.fn.fnamemodify(path, ":.") .. " to chat context")
								else
									vim.notify("File not readable: " .. path, vim.log.levels.WARN)
								end
							end
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
				-- Add some useful codesearch options
				experimental = true, -- Include experimental directory
				enable_proximity = true, -- Enable proximity search
				max_num_results = 100, -- Increase max results
			}

			telescope.extensions.codesearch.find_query(picker_opts)
		end,
		description = "Add files from CodeSearch to context",
		opts = {
			contains_code = true,
		},
	},
	bugs = {
		keymaps = {
			modes = { i = "<c-g>b", n = "gB" },
		},
		callback = function(chat)
			-- Prompt user for bug query
			vim.ui.input({
				prompt = "Bug query: ",
				default = "",
			}, function(query)
				if not query or query == "" then
					vim.notify("No query provided", vim.log.levels.WARN)
					return
				end

				-- Create bugs directory if it doesn't exist
				local bugs_dir = vim.fn.expand("~/.local/share/nvim/codecompanion/bugs")
				vim.fn.mkdir(bugs_dir, "p")

				-- Generate timestamp in YYMMDD_HHMMSS format
				local timestamp = os.date("%y%m%d_%H%M%S")
				local output_file = bugs_dir .. "/bug_" .. timestamp .. ".md"

				-- Run bug_show script with the query
				local cmd = { vim.env.HOME .. "/bin/bug_show", query }
				---@diagnostic disable-next-line: missing-fields
				local job = require("plenary.job"):new({
					command = cmd[1],
					args = { cmd[2] },
					on_exit = function(j, return_val)
						if return_val == 0 then
							local stdout = j:result()
							local stderr = j:stderr_result()
							local content = table.concat(stdout, "\n")
							local stderr_content = table.concat(stderr, "\n")

							if stderr_content and stderr_content ~= "" then
								vim.notify("STDERR: " .. stderr_content, vim.log.levels.WARN)
							end

							-- Write output to file
							local file = io.open(output_file, "w")
							if file then
								file:write(content)
								file:close()

								-- Schedule the buffer operations for the main event loop
								vim.schedule(function()
									-- Add content to chat as reference
									chat:add_reference({
										role = "user",
										content = string.format("Bug Query: %s\n\n```\n%s\n```", query, content),
									}, "bug", output_file)

									vim.notify("Bug query results saved to " .. output_file .. " and added to chat")
								end)
							else
								vim.schedule(function()
									vim.notify("Failed to write to " .. output_file, vim.log.levels.ERROR)
								end)
							end
						else
							local stderr = j:stderr_result()
							local error_msg = table.concat(stderr, "\n")
							vim.schedule(function()
								vim.notify("bug_show command failed: " .. error_msg, vim.log.levels.ERROR)
							end)
						end
					end,
				})

				job:start()
			end)
		end,
		description = "Query bugs using bug_show script and save results",
		opts = {
			contains_code = false,
		},
	},
}
