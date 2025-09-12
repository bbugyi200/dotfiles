--- CodeCompanion /xfile slash command.
---
--- Allows users to select xfile targets and add resolved files to the chat context.
--- xfiles contain targets (one per line) which can be:
--- - File paths (absolute or relative to cwd)
--- - Glob patterns (relative to cwd)
--- - Directory paths (absolute or relative to cwd)
--- - Shell commands in [[filename]] command format
--- - xfile references in x:filename format

local xfiles_dir = vim.fn.expand("~/.local/share/nvim/codecompanion/user/xfiles")

--- Ensure the xfiles directory exists
local function ensure_xfiles_dir()
	vim.fn.mkdir(xfiles_dir, "p")
end

--- Parse and resolve a target line to file paths
---@param target_line string
---@param processed_xfiles? table Track processed xfiles to prevent infinite recursion
---@return table List of resolved file paths
local function resolve_target(target_line, processed_xfiles)
	processed_xfiles = processed_xfiles or {}
	local resolved_files = {}
	local trimmed = vim.trim(target_line)

	if trimmed == "" or vim.startswith(trimmed, "#") then
		return resolved_files
	end

	-- Check if it's an xfile reference
	local xfile_ref = trimmed:match("^x:(.+)$")
	if xfile_ref then
		local xfile_path = xfiles_dir .. "/" .. xfile_ref .. ".txt"

		-- Prevent infinite recursion
		if processed_xfiles[xfile_path] then
			vim.notify("Circular xfile reference detected: " .. xfile_ref, vim.log.levels.WARN)
			return resolved_files
		end

		-- Check if referenced xfile exists
		if vim.fn.filereadable(xfile_path) ~= 1 then
			vim.notify("Referenced xfile not found: " .. xfile_ref .. ".txt", vim.log.levels.WARN)
			return resolved_files
		end

		-- Mark this xfile as being processed
		processed_xfiles[xfile_path] = true

		-- Read and process the referenced xfile
		local file = io.open(xfile_path, "r")
		if file then
			local content = file:read("*all")
			file:close()

			local lines = vim.split(content, "\n")
			for _, line in ipairs(lines) do
				local ref_resolved = resolve_target(line, processed_xfiles)
				for _, ref_file in ipairs(ref_resolved) do
					table.insert(resolved_files, ref_file)
				end
			end
		else
			vim.notify("Failed to read referenced xfile: " .. xfile_ref .. ".txt", vim.log.levels.ERROR)
		end

		-- Unmark this xfile after processing (allows it to be referenced again in different branches)
		processed_xfiles[xfile_path] = nil

		return resolved_files
	end

	-- Check if it's a shell command
	local shell_filename, shell_cmd = trimmed:match("^%[%[(.+)%]%]%s*(.+)$")
	if shell_filename and shell_cmd then
		-- Execute shell command and create a temporary file with the output
		local handle = io.popen(shell_cmd)
		if handle then
			local output = handle:read("*all")
			handle:close()

			-- Create a temporary file with the specified filename
			local timestamp = os.date("%Y-%m-%d %H:%M:%S")
			local temp_dir = vim.fn.fnamemodify(vim.fn.tempname(), ":h")
			local temp_file = temp_dir .. "/" .. shell_filename .. ".txt"
			local file = io.open(temp_file, "w")
			if file then
				file:write(string.format("# Generated from command: %s\n", shell_cmd))
				file:write(string.format("# Timestamp: %s\n\n", timestamp))
				file:write(output)
				file:close()
				table.insert(resolved_files, temp_file)
			end
		end
		return resolved_files
	end

	-- Expand path (handle ~ and environment variables)
	local expanded_path = vim.fn.expand(trimmed)

	-- Check if it's an absolute path or make it relative to cwd
	if not vim.startswith(expanded_path, "/") then
		expanded_path = vim.fn.getcwd() .. "/" .. expanded_path
	end

	-- Check if it contains glob patterns
	if expanded_path:match("[*?%[%]]") then
		-- It's a glob pattern
		local matches = vim.fn.globpath(vim.fn.getcwd(), trimmed, false, true)
		for _, match in ipairs(matches) do
			if vim.fn.filereadable(match) == 1 then
				table.insert(resolved_files, match)
			end
		end
	elseif vim.fn.isdirectory(expanded_path) == 1 then
		-- It's a directory - get all files recursively
		local dir_files = vim.fn.globpath(expanded_path, "**/*", false, true)
		for _, file in ipairs(dir_files) do
			if vim.fn.filereadable(file) == 1 then
				table.insert(resolved_files, file)
			end
		end
	elseif vim.fn.filereadable(expanded_path) == 1 then
		-- It's a regular file
		table.insert(resolved_files, expanded_path)
	end

	return resolved_files
end

return {
	keymaps = {
		modes = { i = "<c-x>", n = "gx" },
	},
	callback = function(chat)
		ensure_xfiles_dir()

		-- Get all xfile .txt files
		local xfiles = vim.fn.globpath(xfiles_dir, "*.txt", false, true)

		if #xfiles == 0 then
			vim.notify("No xfiles found in " .. xfiles_dir, vim.log.levels.WARN)
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
						return {
							value = entry,
							display = vim.fn.fnamemodify(entry, ":t"),
							ordinal = vim.fn.fnamemodify(entry, ":t"),
							path = entry,
						}
					end,
				}),
				sorter = conf.file_sorter({}),
				previewer = conf.file_previewer({}),
				attach_mappings = function(prompt_bufnr, _)
					actions.select_default:replace(function()
						local selection = action_state.get_selected_entry()
						actions.close(prompt_bufnr)

						if not selection then
							vim.notify("No xfile selected", vim.log.levels.WARN)
							return
						end

						local xfile_path = selection.value

						-- Read the xfile content
						local file = io.open(xfile_path, "r")
						if not file then
							vim.notify("Failed to read xfile: " .. xfile_path, vim.log.levels.ERROR)
							return
						end

						local content = file:read("*all")
						file:close()

						-- Process each line as a target (with recursion tracking)
						local all_resolved_files = {}
						local lines = vim.split(content, "\n")
						local processed_xfiles = {}

						for _, line in ipairs(lines) do
							local resolved_files = resolve_target(line, processed_xfiles)
							for _, resolved_file in ipairs(resolved_files) do
								table.insert(all_resolved_files, resolved_file)
							end
						end

						if #all_resolved_files == 0 then
							vim.notify("No files resolved from xfile targets", vim.log.levels.WARN)
							return
						end

						-- Add each resolved file to the chat context
						local added_count = 0
						for _, file_path in ipairs(all_resolved_files) do
							if vim.fn.filereadable(file_path) == 1 then
								-- Read the file content
								local file_content = table.concat(vim.fn.readfile(file_path), "\n")

								-- Add the file as a reference to the chat
								chat:add_reference({
									role = "user",
									content = string.format(
										"File: %s\n\n```%s\n%s\n```",
										vim.fn.fnamemodify(file_path, ":~"),
										vim.fn.fnamemodify(file_path, ":e"),
										file_content
									),
								}, "file", file_path)

								added_count = added_count + 1
							else
								vim.notify("File not readable: " .. file_path, vim.log.levels.WARN)
							end
						end

						local xfile_name = vim.fn.fnamemodify(xfile_path, ":t:r")
						vim.notify(
							string.format("Added %d files from xfile '%s' to chat context", added_count, xfile_name),
							vim.log.levels.INFO
						)
					end)

					return true
				end,
			})
			:find()
	end,
	description = "Add files from xfile targets to context",
}
