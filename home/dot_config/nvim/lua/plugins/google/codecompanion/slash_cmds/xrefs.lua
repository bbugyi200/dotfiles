--- CodeCompanion /xref slash command.
---
--- Allows users to find references to a symbol using the xref_files script.
--- The symbol can be provided as input or defaults to clipboard contents.
--- All files containing references to the symbol are added to the chat context.

return {
	keymaps = {
		modes = { i = "<c-g>xr", n = "gxr" },
	},
	---@diagnostic disable-next-line: undefined-doc-name
	---@param chat CodeCompanion.Chat
	callback = function(chat)
		-- Check if xref_files command exists
		if vim.fn.executable("xref_files") ~= 1 then
			vim.notify("xref_files command not found in PATH", vim.log.levels.ERROR)
			return
		end

		-- Show current clipboard contents as notification
		local shared = require("plugins.codecompanion.slash_cmds.shared")
		local clipboard_content = shared.get_clipboard_contents()

		if clipboard_content and vim.trim(clipboard_content) ~= "" then
			-- Truncate long clipboard content for notification
			local display_content = clipboard_content
			if #display_content > 100 then
				display_content = display_content:sub(1, 100) .. "..."
			end
			-- Remove newlines for cleaner notification
			display_content = display_content:gsub("\n", " ")

			vim.notify("CLIPBOARD: " .. display_content, vim.log.levels.INFO, { title = "XRefs" })
		else
			vim.notify("Clipboard is empty!", vim.log.levels.WARN, { title = "XRefs" })
			return
		end

		-- Always run xref_files without arguments
		local cmd = { "xref_files" }
		---@diagnostic disable-next-line: missing-fields
		local job = require("plenary.job"):new({
			command = cmd[1],
			args = {},
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
							vim.notify("No readable files found from xref_files", vim.log.levels.WARN)
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
								prompt_title = string.format("XRef Files (%d files)", #file_paths),
								finder = finders.new_table({
									results = file_paths,
									entry_maker = function(entry)
										return {
											value = entry,
											display = vim.fn.fnamemodify(entry, ":~"),
											ordinal = vim.fn.fnamemodify(entry, ":~"),
											path = entry,
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

													---@diagnostic disable-next-line: undefined-field
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
													---@diagnostic disable-next-line: undefined-field
													chat.context:add({
														id = id,
														path = path,
														source = "codecompanion.strategies.chat.slash_commands.xrefs",
													})

													added_count = added_count + 1
													vim.notify(
														"Added " .. vim.fn.fnamemodify(path, ":~") .. " to chat context"
													)
												else
													vim.notify("File not readable: " .. path, vim.log.levels.WARN)
												end
											end

											if added_count > 0 then
												vim.notify(
													string.format("Added %d files to chat context", added_count),
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

									-- Select all items
									map("i", "<C-a>", actions.select_all)
									map("n", "<C-a>", actions.select_all)

									return true
								end,
							})
							:find()
					end)
				else
					local stderr = j:stderr_result()
					local error_msg = table.concat(stderr, "\n")
					vim.schedule(function()
						vim.notify("xref_files command failed: " .. error_msg, vim.log.levels.ERROR)
					end)
				end
			end,
		})

		job:start()
	end,
	description = "Find files using xref_files and select which to add to context",
	opts = {
		contains_code = true,
	},
}
