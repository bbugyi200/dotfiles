--- Shared utilities for CodeCompanion slash commands

local M = {}

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

	return M.process_filepaths(filepaths, chat, source_name)
end

--- Process a list of filepaths and add them to chat context
---@param filepaths table List of filepaths to process
---@param chat table The CodeCompanion chat object
---@param source_name string The source name for context tracking (e.g., "paths", "xpath")
---@return number, table Number of files added and list of failed files
function M.process_filepaths(filepaths, chat, source_name)
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

return M