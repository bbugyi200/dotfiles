--- Shared utilities for CodeCompanion slash commands

local M = {}

--- Process a list of filepaths and add them to chat context
---@param filepaths table List of filepaths to process
---@param chat table The CodeCompanion chat object
---@param source_name string The source name for context tracking (e.g., "paths", "xpath")
---@return number, table Number of files added and list of failed files
local function process_filepaths(filepaths, chat, source_name)
	if #filepaths == 0 then
		return 0, {}
	end

	local added_count = 0
	local failed_files = {}

	-- Process each filepath
	for _, filepath in ipairs(filepaths) do
		-- Expand path (handle ~ and environment variables)
		local expanded_path = vim.fn.expand(filepath)

		-- Convert relative paths to absolute paths based on cwd
		if not vim.startswith(expanded_path, "/") then
			expanded_path = vim.fn.getcwd() .. "/" .. expanded_path
		end

		if vim.fn.filereadable(expanded_path) == 1 then
			-- Read the file content
			local content = table.concat(vim.fn.readfile(expanded_path), "\n")
			local relative_path = vim.fn.fnamemodify(expanded_path, ":~")
			local ft = vim.fn.fnamemodify(expanded_path, ":e")
			local id = "<file>" .. relative_path .. "</file>"

			-- Add the file as a message to the chat
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
				path = expanded_path,
				context_id = id,
				tag = "file",
				visible = false,
			})

			-- Add to context tracking
			chat.context:add({
				id = id,
				path = expanded_path,
				source = "codecompanion.strategies.chat.slash_commands." .. source_name,
			})

			added_count = added_count + 1
		else
			table.insert(failed_files, filepath)
		end
	end

	return added_count, failed_files
end

--- Notify user about file operation results
---@param added_count number Number of files successfully added
---@param failed_files table List of files that failed to be read
local function notify_file_results(added_count, failed_files)
	if added_count > 0 then
		vim.notify(string.format("Added %d files to chat context", added_count), vim.log.levels.INFO)
	end

	if #failed_files > 0 then
		vim.notify(
			string.format("Failed to read %d files: %s", #failed_files, table.concat(failed_files, ", ")),
			vim.log.levels.WARN
		)
	end
end

--- Process multiple filepaths from a whitespace-separated string and add them to chat context
---@param input string The input string containing filepaths separated by whitespace
---@param chat table The CodeCompanion chat object
---@param source_name string The source name for context tracking (e.g., "paths", "xpath")
---@return number, table Number of files added and list of failed files
function M.process_filepaths_from_string(input, chat, source_name)
	if not input or vim.trim(input) == "" then
		return 0, {}
	end

	-- Split input by whitespace to get individual filepaths
	local filepaths = {}
	for filepath in input:gmatch("%S+") do
		table.insert(filepaths, filepath)
	end

	return process_filepaths(filepaths, chat, source_name)
end

--- Get clipboard contents using the appropriate command for the platform
---@return string|nil The clipboard contents, or nil if failed
function M.get_clipboard_contents()
	local clipboard_cmd
	if vim.fn.has("mac") == 1 then
		clipboard_cmd = "pbpaste"
	else
		clipboard_cmd = "xclip -o -sel clipboard"
	end

	local clipboard_handle = io.popen(clipboard_cmd)
	if not clipboard_handle then
		vim.notify("Failed to execute clipboard command: " .. clipboard_cmd, vim.log.levels.ERROR)
		return nil
	end

	local content = clipboard_handle:read("*all")
	clipboard_handle:close()

	return content
end

--- Create a telescope picker for file selection with common functionality
---@param title string The title for the picker
---@param files table List of files to display
---@param chat table The CodeCompanion chat object
---@param source_name string The source name for context tracking
---@param options? table Optional configuration
function M.create_file_picker(title, files, chat, source_name, options)
	options = options or {}

	local pickers = require("telescope.pickers")
	local finders = require("telescope.finders")
	local conf = require("telescope.config").values
	local actions = require("telescope.actions")
	local action_state = require("telescope.actions.state")

	pickers
		.new({}, {
			prompt_title = title,
			finder = finders.new_table({
				results = files,
				entry_maker = options.entry_maker or function(entry)
					-- Handle both simple paths and complex objects
					local path = type(entry) == "string" and entry or entry.path
					local display = options.display_formatter and options.display_formatter(entry)
						or vim.fn.fnamemodify(path, ":~")

					return {
						value = path,
						display = display,
						ordinal = vim.fn.fnamemodify(path, ":~"),
						path = path,
					}
				end,
			}),
			sorter = conf.file_sorter({}),
			previewer = options.show_preview and conf.file_previewer({}) or nil,
			attach_mappings = function(prompt_bufnr, map)
				actions.select_default:replace(function()
					local paths = M.get_selected_paths(prompt_bufnr)
					actions.close(prompt_bufnr)

					if #paths > 0 then
						M.add_files_to_chat(paths, chat, source_name)
					else
						vim.notify("No files selected", vim.log.levels.WARN)
					end
				end)

				M.setup_common_keymaps(map, actions)

				-- Add any custom keymaps from options
				if options.custom_keymaps then
					options.custom_keymaps(map, actions, prompt_bufnr)
				end

				return true
			end,
		})
		:find()
end

--- Get selected paths from telescope picker
---@param prompt_bufnr number The telescope prompt buffer number
---@return table List of selected file paths
function M.get_selected_paths(prompt_bufnr)
	local action_state = require("telescope.actions.state")
	local picker = action_state.get_current_picker(prompt_bufnr)
	local multi_selection = picker:get_multi_selection()
	local paths = {}

	if #multi_selection > 0 then
		for _, entry in ipairs(multi_selection) do
			table.insert(paths, entry.value or entry.path)
		end
	else
		local selection = action_state.get_selected_entry()
		if selection then
			table.insert(paths, selection.value or selection.path)
		end
	end

	return paths
end

--- Setup common telescope keymaps for multi-selection
---@param map function The telescope keymap function
---@param actions table Telescope actions
function M.setup_common_keymaps(map, actions)
	-- Allow multi-select with Tab
	map("i", "<Tab>", actions.toggle_selection + actions.move_selection_worse)
	map("n", "<Tab>", actions.toggle_selection + actions.move_selection_worse)
	map("i", "<S-Tab>", actions.toggle_selection + actions.move_selection_better)
	map("n", "<S-Tab>", actions.toggle_selection + actions.move_selection_better)

	-- Select all items
	map("i", "<C-a>", actions.select_all)
	map("n", "<C-a>", actions.select_all)
end

--- Add multiple files to chat context
---@param paths table List of file paths to add
---@param chat table The CodeCompanion chat object
---@param source_name string The source name for context tracking
---@return number, table Number of files added and list of failed files
function M.add_files_to_chat(paths, chat, source_name)
	local added_count = 0
	local failed_files = {}

	for _, path in ipairs(paths) do
		if vim.fn.filereadable(path) == 1 then
			-- Read the file content
			local content = table.concat(vim.fn.readfile(path), "\n")
			local relative_path = vim.fn.fnamemodify(path, ":~")
			local ft = vim.fn.fnamemodify(path, ":e")
			local id = "<file>" .. relative_path .. "</file>"

			-- Add the file as a message to the chat
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
				source = "codecompanion.strategies.chat.slash_commands." .. source_name,
			})

			added_count = added_count + 1
		else
			table.insert(failed_files, path)
		end
	end

	notify_file_results(added_count, failed_files)
	return added_count, failed_files
end

--- Run a command asynchronously and process file results
---@param cmd string The command to run
---@param args table Command arguments
---@param chat table The CodeCompanion chat object
---@param source_name string The source name for context tracking
---@param options table Configuration options
function M.run_command_and_process_files(cmd, args, chat, source_name, options)
	options = options or {}

	local job = require("plenary.job"):new({
		command = cmd,
		args = args,
		on_exit = function(j, return_val)
			if return_val == 0 then
				local stdout = j:result()
				local stderr = j:stderr_result()

				-- Handle stderr output
				if stderr and #stderr > 0 then
					local stderr_content = table.concat(stderr, "\n")
					if stderr_content ~= "" then
						vim.notify("STDERR: " .. stderr_content, vim.log.levels.WARN)
					end
				end

				-- Process output based on options
				if options.process_output then
					local files = options.process_output(stdout)
					vim.schedule(function()
						if #files > 0 then
							local title = string.format("%s (%d files)", options.title or "Files", #files)
							M.create_file_picker(title, files, chat, source_name, options.picker_options)
						else
							vim.notify("No files found", vim.log.levels.WARN)
						end
					end)
				end
			else
				local stderr = j:stderr_result()
				local error_msg = table.concat(stderr, "\n")
				vim.schedule(function()
					vim.notify(cmd .. " command failed: " .. error_msg, vim.log.levels.ERROR)
				end)
			end
		end,
	})

	job:start()
end

return M
