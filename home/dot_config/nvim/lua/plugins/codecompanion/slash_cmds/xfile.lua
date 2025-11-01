--- CodeCompanion /xfile slash command.
---
--- Allows users to select xfile targets and add resolved files to the chat context.
--- Uses the xfile bash script (backed by Python) to process xfiles.

local global_xfiles_dir = vim.fn.expand("~/.local/share/nvim/codecompanion/user/xfiles")
local function get_local_xfiles_dir()
	return vim.fn.getcwd() .. "/xfiles"
end

--- Ensure both global and local xfiles directories exist
local function ensure_xfiles_dirs()
	vim.fn.mkdir(global_xfiles_dir, "p")
	vim.fn.mkdir(get_local_xfiles_dir(), "p")
end

return {
	keymaps = {
		modes = { i = "<c-g>.", n = "g." },
	},
	---@diagnostic disable-next-line: undefined-doc-name
	---@param chat CodeCompanion.Chat
	callback = function(chat)
		ensure_xfiles_dirs()

		-- Get xfiles from both directories with local precedence
		local local_xfiles_dir = get_local_xfiles_dir()
		local local_xfiles = vim.fn.globpath(local_xfiles_dir, "*.txt", false, true)
		local global_xfiles = vim.fn.globpath(global_xfiles_dir, "*.txt", false, true)

		-- Combine files with local precedence (no duplicates based on filename)
		local xfiles = {}
		local seen_filenames = {}

		-- Add local files first (these take precedence)
		for _, file_path in ipairs(local_xfiles) do
			local filename = vim.fn.fnamemodify(file_path, ":t")
			if not seen_filenames[filename] then
				table.insert(xfiles, { path = file_path, location = "local" })
				seen_filenames[filename] = true
			end
		end

		-- Add global files that don't conflict with local ones
		for _, file_path in ipairs(global_xfiles) do
			local filename = vim.fn.fnamemodify(file_path, ":t")
			if not seen_filenames[filename] then
				table.insert(xfiles, { path = file_path, location = "global" })
				seen_filenames[filename] = true
			end
		end

		if #xfiles == 0 then
			vim.notify("No xfiles found in " .. local_xfiles_dir .. " or " .. global_xfiles_dir, vim.log.levels.WARN)
			return
		end

		-- Use telescope for xfile selection
		local pickers = require("telescope.pickers")
		local finders = require("telescope.finders")
		local conf = require("telescope.config").values
		local actions = require("telescope.actions")
		local action_state = require("telescope.actions.state")

		pickers
			.new({}, {
				prompt_title = string.format("Select XFile (%d files)", #xfiles),
				finder = finders.new_table({
					results = xfiles,
					entry_maker = function(entry)
						local filename = vim.fn.fnamemodify(entry.path, ":t")
						local location_indicator = entry.location == "local" and "[L]" or "[G]"
						return {
							value = entry.path,
							display = string.format("%s %s", filename, location_indicator),
							ordinal = filename .. " " .. entry.location,
							path = entry.path,
						}
					end,
				}),
				sorter = conf.file_sorter({}),
				previewer = conf.file_previewer({}),
				attach_mappings = function(prompt_bufnr, map)
					actions.select_default:replace(function()
						local picker = action_state.get_current_picker(prompt_bufnr)
						local multi_selection = picker:get_multi_selection()
						local xfile_names = {}

						-- Handle multi-selection first
						if #multi_selection > 0 then
							for _, entry in ipairs(multi_selection) do
								local name = vim.fn.fnamemodify(entry.value, ":t:r")
								table.insert(xfile_names, name)
							end
						else
							-- Single selection fallback
							local selection = action_state.get_selected_entry()
							if selection then
								local name = vim.fn.fnamemodify(selection.value, ":t:r")
								table.insert(xfile_names, name)
							end
						end

						actions.close(prompt_bufnr)

						if #xfile_names == 0 then
							vim.notify("No xfiles selected", vim.log.levels.WARN)
							return
						end

						-- Call xfile script to process the selected xfiles
						local xfile_args = table.concat(xfile_names, " ")
						local cmd = string.format("xfile --render %s", xfile_args)
						local handle = io.popen(cmd)
						if not handle then
							vim.notify("Failed to execute xfile command", vim.log.levels.ERROR)
							return
						end

						local output = handle:read("*all")
						handle:close()

						if not output or vim.trim(output) == "" then
							vim.notify("No files resolved from selected xfiles", vim.log.levels.WARN)
							return
						end

						-- Parse the output (one file path per line)
						local file_paths = vim.split(vim.trim(output), "\n")
						local added_count = 0
						local rendered_file_path = nil

						-- First file in output is the rendered summary
						if #file_paths > 0 then
							rendered_file_path = file_paths[1]
							-- Add rendered summary to context
							if vim.fn.filereadable(rendered_file_path) == 1 then
								local file_content = table.concat(vim.fn.readfile(rendered_file_path), "\n")
								local relative_path = vim.fn.fnamemodify(rendered_file_path, ":~")
								local id = "<file>" .. relative_path .. "</file>"

								---@diagnostic disable-next-line: undefined-field
								chat:add_message({
									role = "user",
									content = string.format(
										"Here is a rendered summary of the selected xfile(s):\n```md\n%s\n```",
										file_content
									),
								}, {
									path = rendered_file_path,
									context_id = id,
									tag = "file",
									visible = false,
								})

								-- Add to context tracking
								---@diagnostic disable-next-line: undefined-field
								chat.context:add({
									id = id,
									path = rendered_file_path,
									source = "codecompanion.strategies.chat.slash_commands.xfile",
								})

								vim.notify(
									string.format(
										"Created rendered summary: %s",
										vim.fn.fnamemodify(rendered_file_path, ":t")
									),
									vim.log.levels.INFO
								)
								added_count = added_count + 1
							end
						end

						-- Add remaining files to context (skip first file which is the rendered summary)
						for i = 2, #file_paths do
							local file_path = file_paths[i]
							if vim.fn.filereadable(file_path) == 1 then
								-- Read the file content
								local file_content = table.concat(vim.fn.readfile(file_path), "\n")

								-- Add the file as a message to the chat
								local relative_path = vim.fn.fnamemodify(file_path, ":~")
								local ft = vim.fn.fnamemodify(file_path, ":e")
								local id = "<file>" .. relative_path .. "</file>"

								---@diagnostic disable-next-line: undefined-field
								chat:add_message({
									role = "user",
									content = string.format(
										"Here is the content from a file (including line numbers):\n```%s\n%s:%s\n%s\n```",
										ft,
										relative_path,
										relative_path,
										file_content
									),
								}, {
									path = file_path,
									context_id = id,
									tag = "file",
									visible = false,
								})

								-- Add to context tracking
								---@diagnostic disable-next-line: undefined-field
								chat.context:add({
									id = id,
									path = file_path,
									source = "codecompanion.strategies.chat.slash_commands.xfile",
								})

								added_count = added_count + 1
							else
								vim.notify("File not readable: " .. file_path, vim.log.levels.WARN)
							end
						end

						-- Final summary notification
						if added_count > 0 then
							vim.notify(
								string.format(
									"Total: Added %d files from %d xfiles (%s) to chat context",
									added_count,
									#xfile_names,
									table.concat(xfile_names, ", ")
								),
								vim.log.levels.INFO
							)
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
	end,
	description = "Add files from xfile targets to context",
}
