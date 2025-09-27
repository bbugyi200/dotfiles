--- CodeCompanion /bcc slash command.
---
--- Allows users to select files from branch changes (current CL/PR) and branch chain changes
--- (current CL/PR and all ancestor CLs/PRs) and add them to the chat context.
--- Files from branch_changes are marked and shown at the top of the list.

return {
	keymaps = {
		modes = { i = "<c-g>bc", n = "gB" },
	},
	callback = function(chat)
		-- Check if both commands exist
		if vim.fn.executable("branch_changes") ~= 1 then
			vim.notify("branch_changes command not found in PATH", vim.log.levels.ERROR)
			return
		end
		if vim.fn.executable("branch_chain_changes") ~= 1 then
			vim.notify("branch_chain_changes command not found in PATH", vim.log.levels.ERROR)
			return
		end

		-- Run both commands in parallel
		local branch_files = {}
		local chain_files = {}
		local completed_jobs = 0
		local total_jobs = 2

		local function check_completion()
			completed_jobs = completed_jobs + 1
			if completed_jobs == total_jobs then
				-- Both jobs completed, process results
				vim.schedule(function()
					-- Combine files with branch files first (marked)
					local all_files = {}
					local seen_files = {}

					-- Add branch files first (these are marked as current CL/PR)
					for _, file in ipairs(branch_files) do
						if vim.fn.filereadable(file) == 1 and not seen_files[file] then
							table.insert(all_files, { path = file, is_current = true })
							seen_files[file] = true
						end
					end

					-- Add chain files that aren't already in branch files
					for _, file in ipairs(chain_files) do
						if vim.fn.filereadable(file) == 1 and not seen_files[file] then
							table.insert(all_files, { path = file, is_current = false })
							seen_files[file] = true
						end
					end

					if #all_files == 0 then
						vim.notify("No readable files found from branch changes commands", vim.log.levels.WARN)
						return
					end

					-- Use telescope for file selection with multi-select capability
					local pickers = require("telescope.pickers")
					local finders = require("telescope.finders")
					local conf = require("telescope.config").values
					local actions = require("telescope.actions")
					local action_state = require("telescope.actions.state")

					pickers
						.new({}, {
							prompt_title = string.format(
								"Branch Changes (%d current, %d total)",
								#branch_files,
								#all_files
							),
							finder = finders.new_table({
								results = all_files,
								entry_maker = function(entry)
									local marker = entry.is_current and "[L]" or "[G]"
									local relative_path = vim.fn.fnamemodify(entry.path, ":~")
									return {
										value = entry.path,
										display = string.format("%s %s", marker, relative_path),
										ordinal = relative_path,
										path = entry.path,
										is_current = entry.is_current,
									}
								end,
							}),
							sorter = conf.file_sorter({}),
							previewer = conf.file_previewer({}),
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
										local added_count = 0
										for _, path in ipairs(paths) do
											if vim.fn.filereadable(path) == 1 then
												-- Read the file content
												local content = table.concat(vim.fn.readfile(path), "\n")
												local relative_path = vim.fn.fnamemodify(path, ":~")
												local ft = vim.fn.fnamemodify(path, ":e")
												local id = "<file>" .. relative_path .. "</file>"

												chat:add_message({
													role = "user",
													content = string.format(
														"Here is the content from a file (including line numbers):\n```%s\n%s:%s\n%s\n```",
														ft,
														relative_path,
														relative_path,
														content
													),
												}, {
													path = path,
													context_id = id,
													tag = "file",
													visible = false,
												})

												-- Add to context tracking
												chat.context:add({
													id = id,
													path = path,
													source = "codecompanion.strategies.chat.slash_commands.bcc",
												})

												added_count = added_count + 1
											else
												vim.notify("File not readable: " .. path, vim.log.levels.WARN)
											end
										end

										if added_count > 0 then
											vim.notify(
												string.format(
													"Added %d files from branch changes to chat context",
													added_count
												),
												vim.log.levels.INFO
											)
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

								-- Select all current CL files
								map("i", "<C-c>", function()
									local picker = action_state.get_current_picker(prompt_bufnr)
									for i, entry in ipairs(picker.finder.results) do
										if entry.is_current then
											picker:toggle_selection(i)
										end
									end
								end)
								map("n", "<C-c>", function()
									local picker = action_state.get_current_picker(prompt_bufnr)
									for i, entry in ipairs(picker.finder.results) do
										if entry.is_current then
											picker:toggle_selection(i)
										end
									end
								end)

								-- Select all files
								map("i", "<C-a>", actions.select_all)
								map("n", "<C-a>", actions.select_all)

								return true
							end,
						})
						:find()
				end)
			end
		end

		-- Run branch_changes command
		---@diagnostic disable-next-line: missing-fields
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
					local stderr = j:stderr_result()
					local error_msg = table.concat(stderr, "\n")
					vim.schedule(function()
						vim.notify("branch_changes command failed: " .. error_msg, vim.log.levels.ERROR)
					end)
				end
				check_completion()
			end,
		})

		-- Run branch_chain_changes command
		---@diagnostic disable-next-line: missing-fields
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
					local stderr = j:stderr_result()
					local error_msg = table.concat(stderr, "\n")
					vim.schedule(function()
						vim.notify("branch_chain_changes command failed: " .. error_msg, vim.log.levels.ERROR)
					end)
				end
				check_completion()
			end,
		})

		-- Start both jobs
		branch_job:start()
		chain_job:start()
	end,
	description = "Add files from branch changes (current + ancestor CLs/PRs) to context",
	opts = {
		contains_code = true,
	},
}

