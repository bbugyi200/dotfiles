--- CodeCompanion /xfile slash command.
---
--- Allows users to select xfile targets and add resolved files to the chat context.
--- xfiles contain targets (one per line) which can be:
--- - File paths (absolute or relative to cwd)
--- - Glob patterns (relative to cwd)
--- - Directory paths (absolute or relative to cwd)
--- - Shell commands in [[filename]] command format
--- - xfile references in x:filename format

local global_xfiles_dir = vim.fn.expand("~/.local/share/nvim/codecompanion/user/xfiles")
local function get_local_xfiles_dir()
	return vim.fn.getcwd() .. "/xfiles"
end

--- Ensure both global and local xfiles directories exist
local function ensure_xfiles_dirs()
	vim.fn.mkdir(global_xfiles_dir, "p")
	vim.fn.mkdir(get_local_xfiles_dir(), "p")
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
		-- Check local directory first, then global directory
		local local_xfile_path = get_local_xfiles_dir() .. "/" .. xfile_ref .. ".txt"
		local global_xfile_path = global_xfiles_dir .. "/" .. xfile_ref .. ".txt"

		local xfile_path
		if vim.fn.filereadable(local_xfile_path) == 1 then
			xfile_path = local_xfile_path
		elseif vim.fn.filereadable(global_xfile_path) == 1 then
			xfile_path = global_xfile_path
		else
			vim.notify(
				"Referenced xfile not found: " .. xfile_ref .. ".txt (checked both local and global directories)",
				vim.log.levels.WARN
			)
			return resolved_files
		end

		-- Prevent infinite recursion
		if processed_xfiles[xfile_path] then
			vim.notify("Circular xfile reference detected: " .. xfile_ref, vim.log.levels.WARN)
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
		-- Execute shell command and create a file with the output in the current working directory
		local handle = io.popen(shell_cmd)
		if handle then
			local output = handle:read("*all")
			handle:close()

			-- Only create file if output contains non-whitespace content
			if output and vim.trim(output) ~= "" then
				-- Create a file in the current working directory with the specified filename
				local timestamp = os.date("%Y-%m-%d %H:%M:%S")
				-- Use custom extension if provided, otherwise default to .txt
				local filename_with_ext = shell_filename
				if not shell_filename:match("%.%w+$") then
					filename_with_ext = shell_filename .. ".txt"
				end
				local output_file = vim.fn.getcwd() .. "/" .. filename_with_ext
				local file = io.open(output_file, "w")
				if file then
					file:write(string.format("# Generated from command: %s\n", shell_cmd))
					file:write(string.format("# Timestamp: %s\n\n", timestamp))
					file:write(output)
					file:close()
					table.insert(resolved_files, output_file)
				end
			end
		end
		return resolved_files
	end

	-- Check if it contains glob patterns FIRST (before path expansion)
	if trimmed:match("[*?%[%]]") then
		-- It's a glob pattern - use globpath relative to cwd
		local matches = vim.fn.globpath(vim.fn.getcwd(), trimmed, false, true)
		for _, match in ipairs(matches) do
			if vim.fn.filereadable(match) == 1 then
				table.insert(resolved_files, match)
			end
		end
		return resolved_files
	end

	-- Now handle regular files and directories
	-- Expand path (handle ~ and environment variables)
	local expanded_path = vim.fn.expand(trimmed)

	-- Check if it's an absolute path or make it relative to cwd
	if not vim.startswith(expanded_path, "/") then
		expanded_path = vim.fn.getcwd() .. "/" .. expanded_path
	end

	if vim.fn.isdirectory(expanded_path) == 1 then
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
		modes = { i = "<c-g>x", n = "gx" },
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
								---@diagnostic disable-next-line: undefined-field
								chat:add_context({
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
