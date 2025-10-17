--- CodeCompanion /xfile slash command.
---
--- Allows users to select xfile targets and add resolved files to the chat context.
--- Also creates a rendered summary file that shows the processed xfile content.
--- xfiles contain targets (one per line) which can be:
--- - File paths (absolute or relative to cwd)
--- - Glob patterns (relative to cwd)
--- - Directory paths (absolute or relative to cwd)
--- - Shell commands in [[filename]] command format
--- - Commands that output file paths in !command format
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

--- Generate a unique filename for the rendered xfile
---@param xfile_names table List of xfile names being processed
---@return string Unique filename for the rendered file
local function generate_rendered_filename(xfile_names)
	local timestamp = os.date("%y%m%d_%H%M%S")
	local xfile_part = table.concat(xfile_names, "_")
	-- Sanitize filename
	xfile_part = xfile_part:gsub("[^%w_-]", "_")
	return string.format("xfile_rendered_%s_%s.txt", xfile_part, timestamp)
end

--- Render a single target line for the rendered file
---@param target_line string The line to render
---@param processed_xfiles table Track processed xfiles to prevent infinite recursion
---@return string|nil The rendered line, or nil if line should be skipped
local function render_target_line(target_line, processed_xfiles)
	processed_xfiles = processed_xfiles or {}
	local trimmed = vim.trim(target_line)

	-- Preserve blank lines and comments
	if trimmed == "" then
		return ""
	end

	if vim.startswith(trimmed, "#") then
		return trimmed
	end

	-- Handle x:reference
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
			return string.format("# ERROR: Referenced xfile not found: %s.txt", xfile_ref)
		end

		-- Prevent infinite recursion
		if processed_xfiles[xfile_path] then
			return string.format("# ERROR: Circular xfile reference detected: %s", xfile_ref)
		end

		-- Mark this xfile as being processed
		processed_xfiles[xfile_path] = true

		local result = {}
		-- Read and process the referenced xfile
		local file = io.open(xfile_path, "r")
		if file then
			local content = file:read("*all")
			file:close()

			local lines = vim.split(content, "\n")
			for _, line in ipairs(lines) do
				local rendered_ref_line = render_target_line(line, processed_xfiles)
				if rendered_ref_line then
					table.insert(result, rendered_ref_line)
				end
			end
		else
			table.insert(result, string.format("# ERROR: Failed to read referenced xfile: %s.txt", xfile_ref))
		end

		-- Unmark this xfile after processing
		processed_xfiles[xfile_path] = nil

		return table.concat(result, "\n")
	end

	-- Handle !command that outputs file paths
	local bang_cmd = trimmed:match("^!(.+)$")
	if bang_cmd then
		local result = {}
		table.insert(result, string.format("#\n# COMMAND THAT OUTPUT THESE FILES: %s", bang_cmd))

		-- Execute command and collect file paths
		local handle = io.popen(bang_cmd)
		if handle then
			local output = handle:read("*all")
			handle:close()

			if output and vim.trim(output) ~= "" then
				local lines = vim.split(output, "\n")
				for _, line in ipairs(lines) do
					local file_path = vim.trim(line)
					if file_path ~= "" then
						-- Handle relative vs absolute paths
						local expanded_path = vim.fn.expand(file_path)
						if not vim.startswith(expanded_path, "/") then
							expanded_path = vim.fn.getcwd() .. "/" .. expanded_path
						end

						if vim.fn.filereadable(expanded_path) == 1 then
							local relative_path = vim.fn.fnamemodify(expanded_path, ":~")
							table.insert(result, relative_path)
						end
					end
				end
			else
				table.insert(result, "# No output from command")
			end
		else
			table.insert(result, "# ERROR: Failed to execute command")
		end

		return table.concat(result, "\n")
	end

	-- Handle [[filename]] command format
	local shell_filename, shell_cmd = trimmed:match("^%[%[(.+)%]%]%s*(.+)$")
	if shell_filename and shell_cmd then
		-- Process command substitution in the filename
		local processed_filename = shell_filename
		processed_filename = processed_filename:gsub("%$%(([^)]+)%)", function(cmd_substitution)
			local sub_handle = io.popen(cmd_substitution)
			if sub_handle then
				local sub_output = sub_handle:read("*all")
				sub_handle:close()
				return vim.trim(sub_output)
			end
			return ""
		end)

		-- Use custom extension if provided, otherwise default to .txt
		local filename_with_ext = processed_filename
		if not processed_filename:match("%.%w+$") then
			filename_with_ext = processed_filename .. ".txt"
		end

		local xcmds_dir = vim.fn.getcwd() .. "/xcmds"
		local output_file = xcmds_dir .. "/" .. filename_with_ext
		local relative_path = vim.fn.fnamemodify(output_file, ":~")

		-- Execute shell command first to check if it produces output
		local handle = io.popen(shell_cmd)
		if handle then
			local output = handle:read("*all")
			handle:close()

			-- Only show the file path if output contains non-whitespace content
			if output and vim.trim(output) ~= "" then
				return string.format("#\n# COMMAND THAT GENERATED THIS FILE: %s\n%s", shell_cmd, relative_path)
			else
				return string.format("#\n# COMMAND PRODUCED NO OUTPUT: %s", shell_cmd)
			end
		else
			return string.format("#\n# COMMAND FAILED: %s", shell_cmd)
		end
	end

	-- Handle regular files, directories, and glob patterns
	local expanded_path = vim.fn.expand(trimmed)
	if not vim.startswith(expanded_path, "/") then
		expanded_path = vim.fn.getcwd() .. "/" .. expanded_path
	end

	-- Check if it contains glob patterns (ignore if shell command was used)
	if not shell_filename and trimmed:match("[*?%[%]]") then
		local result = {}
		table.insert(result, string.format("#\n# GLOB PATTERN: %s", trimmed))

		local matches = vim.fn.globpath(vim.fn.getcwd(), trimmed, false, true)
		for _, match in ipairs(matches) do
			if vim.fn.filereadable(match) == 1 then
				local relative_path = vim.fn.fnamemodify(match, ":~")
				table.insert(result, relative_path)
			end
		end

		if #result == 1 then
			table.insert(result, "# No files matched")
		end

		return table.concat(result, "\n")
	end

	if vim.fn.isdirectory(expanded_path) == 1 then
		local result = {}
		table.insert(result, string.format("#\n# DIRECTORY: %s", trimmed))

		local dir_files = vim.fn.globpath(expanded_path, "**/*", false, true)
		local count = 0
		for _, file in ipairs(dir_files) do
			if vim.fn.filereadable(file) == 1 then
				local relative_path = vim.fn.fnamemodify(file, ":~")
				table.insert(result, relative_path)
				count = count + 1
			end
		end

		if count == 0 then
			table.insert(result, "# No readable files in directory")
		end

		return table.concat(result, "\n")
	elseif vim.fn.filereadable(expanded_path) == 1 then
		local relative_path = vim.fn.fnamemodify(expanded_path, ":~")
		return relative_path
	else
		return string.format("# ERROR: File not found or not readable: %s", trimmed)
	end
end

--- Create a rendered file that shows the processed xfile content
---@param xfile_paths table List of xfile paths being processed
---@param xfile_names table List of xfile names (without extension)
---@return string|nil Path to the created rendered file, or nil if failed
local function create_rendered_file(xfile_paths, xfile_names)
	local rendered_content = {}

	-- Add file header
	table.insert(
		rendered_content,
		"# ----------------------------------------------------------------------------------"
	)
	table.insert(
		rendered_content,
		"# This file contains a summary of some of the files that have been added to context."
	)
	table.insert(
		rendered_content,
		"# ----------------------------------------------------------------------------------\n"
	)

	-- Process each xfile
	for i, xfile_path in ipairs(xfile_paths) do
		if i > 1 then
			table.insert(rendered_content, "")
			table.insert(rendered_content, "---")
			table.insert(rendered_content, "")
		end

		-- Read and process the xfile content
		local file = io.open(xfile_path, "r")
		if not file then
			table.insert(rendered_content, string.format("ERROR: Failed to read xfile: %s", xfile_path))
			goto continue
		end

		local content = file:read("*all")
		file:close()

		local lines = vim.split(content, "\n")
		local processed_xfiles = {}

		for _, line in ipairs(lines) do
			local rendered_line = render_target_line(line, processed_xfiles)
			if rendered_line then
				table.insert(rendered_content, rendered_line)
			end
		end

		::continue::
	end

	-- Create the rendered file
	local filename = generate_rendered_filename(xfile_names)
	local xcmds_dir = vim.fn.getcwd() .. "/xcmds"
	vim.fn.mkdir(xcmds_dir, "p")
	local rendered_file_path = xcmds_dir .. "/" .. filename

	local file = io.open(rendered_file_path, "w")
	if not file then
		vim.notify("Failed to create rendered file: " .. rendered_file_path, vim.log.levels.ERROR)
		return nil
	end

	file:write(table.concat(rendered_content, "\n"))
	file:close()

	return rendered_file_path
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

	-- Check if it's a command that outputs file paths (new !command syntax)
	local bang_cmd = trimmed:match("^!(.+)$")
	if bang_cmd then
		-- Execute command and treat each line of output as a file path
		local handle = io.popen(bang_cmd)
		if handle then
			local output = handle:read("*all")
			handle:close()

			if output and vim.trim(output) ~= "" then
				local lines = vim.split(output, "\n")
				for _, line in ipairs(lines) do
					local file_path = vim.trim(line)
					if file_path ~= "" then
						-- Handle relative vs absolute paths
						local expanded_path = vim.fn.expand(file_path)
						if not vim.startswith(expanded_path, "/") then
							expanded_path = vim.fn.getcwd() .. "/" .. expanded_path
						end

						if vim.fn.filereadable(expanded_path) == 1 then
							table.insert(resolved_files, expanded_path)
						end
					end
				end
			end
		end
		return resolved_files
	end

	-- Check if it's a shell command
	local shell_filename, shell_cmd = trimmed:match("^%[%[(.+)%]%]%s*(.+)$")
	if shell_filename and shell_cmd then
		-- Process command substitution in the filename
		-- This will handle patterns like foo_$(echo bar) by executing the command and substituting
		local processed_filename = shell_filename
		processed_filename = processed_filename:gsub("%$%(([^)]+)%)", function(cmd_substitution)
			local sub_handle = io.popen(cmd_substitution)
			if sub_handle then
				local sub_output = sub_handle:read("*all")
				sub_handle:close()
				-- Remove trailing whitespace/newlines from command output
				return vim.trim(sub_output)
			end
			return ""
		end)

		-- Execute shell command and create a file with the output in the current working directory
		local handle = io.popen(shell_cmd)
		if handle then
			local output = handle:read("*all")
			handle:close()

			-- Only create file if output contains non-whitespace content
			if output and vim.trim(output) ~= "" then
				-- Create a file in the current working directory with the processed filename
				local timestamp = os.date("%Y-%m-%d %H:%M:%S")
				-- Use custom extension if provided, otherwise default to .txt
				local filename_with_ext = processed_filename
				if not processed_filename:match("%.%w+$") then
					filename_with_ext = processed_filename .. ".txt"
				end
				local xcmds_dir = vim.fn.getcwd() .. "/xcmds"
				vim.fn.mkdir(xcmds_dir, "p")
				local output_file = xcmds_dir .. "/" .. filename_with_ext
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
						local xfile_paths = {}

						-- Handle multi-selection first
						if #multi_selection > 0 then
							for _, entry in ipairs(multi_selection) do
								table.insert(xfile_paths, entry.value)
							end
						else
							-- Single selection fallback
							local selection = action_state.get_selected_entry()
							if selection then
								table.insert(xfile_paths, selection.value)
							end
						end

						actions.close(prompt_bufnr)

						if #xfile_paths == 0 then
							vim.notify("No xfiles selected", vim.log.levels.WARN)
							return
						end

						-- Create rendered file first
						local xfile_names = {}
						for _, xfile_path in ipairs(xfile_paths) do
							table.insert(xfile_names, vim.fn.fnamemodify(xfile_path, ":t:r"))
						end

						local rendered_file_path = create_rendered_file(xfile_paths, xfile_names)
						if rendered_file_path then
							-- Add rendered file to context first
							local rendered_content = table.concat(vim.fn.readfile(rendered_file_path), "\n")
							local rendered_relative_path = vim.fn.fnamemodify(rendered_file_path, ":~")
							local rendered_id = "<file>" .. rendered_relative_path .. "</file>"

							---@diagnostic disable-next-line: undefined-field
							chat:add_message({
								role = "user",
								content = string.format(
									"Here is a rendered summary of the selected xfile(s):\n```md\n%s\n```",
									rendered_content
								),
							}, {
								path = rendered_file_path,
								context_id = rendered_id,
								tag = "file",
								visible = false,
							})

							-- Add to context tracking
							---@diagnostic disable-next-line: undefined-field
							chat.context:add({
								id = rendered_id,
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
						end

						-- Process each selected xfile
						local total_added_count = 0
						for _, xfile_path in ipairs(xfile_paths) do
							-- Read the xfile content
							local file = io.open(xfile_path, "r")
							if not file then
								vim.notify("Failed to read xfile: " .. xfile_path, vim.log.levels.ERROR)
								goto continue
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
								local xfile_name = vim.fn.fnamemodify(xfile_path, ":t:r")
								vim.notify(
									"No files resolved from xfile '" .. xfile_name .. "' targets",
									vim.log.levels.WARN
								)
								goto continue
							end

							-- Add each resolved file to the chat context
							local added_count = 0
							for _, file_path in ipairs(all_resolved_files) do
								if vim.fn.filereadable(file_path) == 1 then
									-- Read the file content
									local file_content = table.concat(vim.fn.readfile(file_path), "\n")

									-- Add the file as a message to the chat (similar to built-in /file command)
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

							total_added_count = total_added_count + added_count
							local xfile_name = vim.fn.fnamemodify(xfile_path, ":t:r")
							vim.notify(
								string.format("Added %d files from xfile '%s'", added_count, xfile_name),
								vim.log.levels.INFO
							)

							::continue::
						end

						-- Final summary notification
						if total_added_count > 0 then
							local summary_parts = {}
							table.insert(
								summary_parts,
								string.format(
									"%d files from %d xfiles (%s)",
									total_added_count,
									#xfile_paths,
									table.concat(xfile_names, ", ")
								)
							)

							if rendered_file_path then
								table.insert(summary_parts, "1 rendered summary")
							end

							vim.notify(
								string.format("Total: Added %s to chat context", table.concat(summary_parts, " + ")),
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
