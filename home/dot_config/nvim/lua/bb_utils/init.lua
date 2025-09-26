--- Neovim utility functions live here!

local M = {}

--- Get the default session name used for saving/loading.
---
--- This function has 3 behaviors depending on whether the current directory is
--- under version-control:
---
--- 1) If this directory is version-controlled using git, the session name will
---    be <parent_dir>/<dir>@<git_branch>, where <parent_dir> is the basename
---    of the current directory's parent and <dir> is the basename of the
---    current directory. For example: in the git directory /path/to/foo/bar,
---    when the master branch is checked out, the session name should be
---    foo/bar@master.
--- 2) If this directory is version-controlled using mercurial, the session
---    name will be <parent_dir>@<commit_name>, where <commit_name> is
---    determined by calling the external `get_fig_commit_name` command and
---    reading its output.
--- 3) If the directory is NOT version controlled, the full path to the current
---    working directory is used.
---
---@return string # The session name.
function M.get_default_session_name()
	-- Check if we're in a git repository
	local is_git = vim.fn.system("git rev-parse --is-inside-work-tree 2>/dev/null"):match("true")
	if is_git then
		-- Get the git branch name
		local branch = vim.fn.system("git branch --show-current 2>/dev/null"):gsub("\n", "")

		-- Get current directory name
		local dir = vim.fn.fnamemodify(vim.fn.getcwd(), ":t")

		-- Get parent directory name
		local parent_dir = vim.fn.fnamemodify(vim.fn.getcwd(), ":h:t")

		-- Return the formatted session name: parent_dir/dir@branch
		return parent_dir .. "/" .. dir .. "@" .. branch
	end

	-- Check if we're in a mercurial repository
	local is_hg = vim.fn.system("hg root 2>/dev/null"):match("^%s*$") == nil
	if is_hg then
		-- Get the commit name using the external command
		local commit_name = vim.fn.system("get_fig_commit_name 2>/dev/null"):gsub("\n", "")

		-- Get parent directory name
		local parent_dir = vim.fn.fnamemodify(vim.fn.getcwd(), ":h:t")

		-- Return the formatted session name: parent_dir@commit_name
		return parent_dir .. "@" .. commit_name
	end

	-- If not in a version-controlled directory, use the full path to the current working directory
	return vim.fn.getcwd()
end

--- Cached result of the Google machine check
M._is_goog_machine_cached_result = nil

--- Check whether NeoVim is being run from a Google machine.
---
---@return boolean # True if and only if I am on a Google machine.
function M.is_goog_machine()
	if M._is_goog_machine_cached_result ~= nil then
		return M._is_goog_machine_cached_result
	end

	local handle = assert(io.popen("uname -a"))
	local result = handle:read("*a")
	handle:close()

	-- Cache the result for future calls
	M._is_goog_machine_cached_result = result:match("googlers") ~= nil

	return M._is_goog_machine_cached_result
end

---@alias BufferDirection
---| "#" The last active buffer.
---| "next" The next buffer.
---| "prev" The previous buffer.
---
--- Remove a buffer and navigate to another buffer specified via {direction}.
---
---@param direction BufferDirection A string indicating a relative buffer direction.
function M.kill_buffer(direction)
	vim.cmd("b" .. direction .. " | sp | b# | bd")
end

--- Wrapper around `vim.api.nvim_feedkeys()`.
---
---@param keys string The keys to type in normal mode.
function M.feedkeys(keys)
	vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(keys, true, true, true), "n", true)
end

--- Helper to copy text to the system clipboard
---
---@param text string The text to copy to the clipboard.
---@param should_append? boolean Whether to append the text to the clipboard.
function M.copy_to_clipboard(text, should_append)
	local msg_prefix, new_clip
	if should_append then
		msg_prefix = "APPENDED TO CLIPBOARD"
		local old_clip = vim.fn.getreg("+")
		new_clip = old_clip .. text
	else
		msg_prefix = "COPIED"
		new_clip = text
	end
	vim.fn.setreg("+", new_clip)
	vim.notify(msg_prefix .. ": " .. text)
end

--- Function to remove the current file using 'trash' with a fallback of 'rm'.
---
---@param filename string The name of the file to delete. Defaults to the current file.
---@return boolean # Whether the file was removed successfully.
function M.delete_file(filename)
	if filename == nil then
		-- Get the current file's full path
		filename = vim.fn.expand("%:p")
		-- Remove the current buffer and navigate back to the last active buffer.
		M.kill_buffer("#")
	end

	-- Create a temporary file for stderr.
	local stderr_file = os.tmpname()

	-- Try to trash the file first.
	local command_name = "trash"
	local trash_success = os.execute(command_name .. " " .. vim.fn.shellescape(filename) .. " 2> " .. stderr_file)

	--- Notify the user that the trash/rm command failed (include error message).
	---
	---@param cmd_name string The name of the command that failed.
	local function notify_cmd_failed(cmd_name)
		local err_msg = io.open(stderr_file, "r"):read("*a")
		vim.notify(err_msg, vim.log.levels.WARN, { title = "'" .. cmd_name .. "' error message" })
	end

	-- If trash command fails, try using rm as fallback.
	if trash_success ~= 0 then
		command_name = "rm"
		local rm_success = os.execute(command_name .. " " .. vim.fn.shellescape(filename) .. " 2> " .. stderr_file)

		-- If both commands fail, show error message.
		if rm_success ~= 0 then
			notify_cmd_failed(command_name)
			vim.notify("Failed to delete file: " .. filename, vim.log.levels.ERROR)
			return false
		end
	end

	vim.notify("Deleted file using '" .. command_name .. "': " .. filename, vim.log.levels.INFO)
	return true
end

--- Quits a "fake buffer" (e.g. a help window or quickfix window).
---
---@param close_window_if_multiple? boolean Whether to close the window if there are multiple windows.
function M.quit_special_buffer(close_window_if_multiple)
	local altfile = vim.fn.expand("%")
	local listed_buffers = vim.fn.getbufinfo({ buflisted = 1 })
	if close_window_if_multiple and #vim.api.nvim_list_wins() > 1 then
		vim.cmd.close()
	elseif altfile ~= "" and vim.fn.filereadable(altfile) then
		vim.cmd("b#")
		-- HACK: Run 'edit' to reload the buffer, which fixes some highlighting
		-- issues at times. Check if the buffer is changed first to avoid "No
		-- write since last change" error.
		if vim.fn.getbufinfo(vim.fn.bufname())[1].changed ~= 1 then
			vim.cmd("edit")
		end
	elseif #listed_buffers > 1 then
		vim.cmd("bd")
	else
		vim.cmd("q")
	end
end

--- Creates a normal-mode keymap that is repeatable via the `.` command.
---
---@param name string A unique name for the intermediate <Plug> mapping.
---@param lhs string The left-hand side of the keymap.
---@param rhs string The right-hand side of the keymap.
---@param opts table<string, any> Table of keymap options (ex: desc).
function M.repeatable_nmap(name, lhs, rhs, opts)
	-- map unique Plug mapping using tostring of function
	local plug_lhs = "<Plug>" .. name
	-- mapping including vim-repeat magic
	local repeat_rhs = plug_lhs .. [[:silent! call repeat#set("\]] .. plug_lhs .. [[", v:count)<CR>]]
	vim.keymap.set("n", plug_lhs, rhs)
	vim.keymap.set("n", lhs, repeat_rhs, opts)
end

--- Run a command that outputs file paths and present them via Telescope with multi-select.
---
--- This function executes the given command, expects newline-separated file paths as output,
--- and presents them in a Telescope picker allowing multi-selection. Returns selected paths.
---
---@param command_name string The shell command to execute (e.g., "find . -name '*.txt'")
---@param opts? table Optional Telescope picker options
---@return table<string> # Table of selected file paths
function M.telescope_command_files(command_name, opts)
	local pickers = require("telescope.pickers")
	local finders = require("telescope.finders")
	local conf = require("telescope.config").values
	local actions = require("telescope.actions")
	local action_state = require("telescope.actions.state")

	opts = opts or {}

	-- Execute the command and capture output
	local handle = io.popen(command_name .. " 2>/dev/null")
	if not handle then
		vim.notify("Failed to execute command: " .. command_name, vim.log.levels.ERROR)
		return {}
	end

	local output = handle:read("*a")
	local exit_code = handle:close()

	if not exit_code then
		vim.notify("Command failed: " .. command_name, vim.log.levels.ERROR)
		return {}
	end

	-- Split output into lines and filter out empty lines
	local files = {}
	for line in output:gmatch("[^\r\n]+") do
		if line:match("%S") then -- Only add non-empty lines
			table.insert(files, line)
		end
	end

	if #files == 0 then
		vim.notify("No files found from command: " .. command_name, vim.log.levels.WARN)
		return {}
	end

	-- Variable to store selected files
	local selected_files = {}

	-- Custom action to collect selections and close
	local function collect_selections(prompt_bufnr)
		local picker = action_state.get_current_picker(prompt_bufnr)
		local selections = picker:get_multi_selection()

		-- If no multi-selections, use the current selection
		if vim.tbl_isempty(selections) then
			local current_selection = action_state.get_selected_entry()
			if current_selection then
				table.insert(selected_files, current_selection.value)
			end
		else
			-- Add all multi-selections
			for _, selection in ipairs(selections) do
				table.insert(selected_files, selection.value)
			end
		end

		actions.close(prompt_bufnr)
	end

	-- Create and run the picker
	pickers
		.new(opts, {
			prompt_title = opts.prompt_title or ("Command Results: " .. command_name),
			finder = finders.new_table({
				results = files,
			}),
			sorter = conf.generic_sorter(opts),
			previewer = conf.file_previewer(opts),
			attach_mappings = function(_, map)
				-- Override default select action
				actions.select_default:replace(collect_selections)

				-- Optional: add explicit multi-select mapping
				map("i", "<C-m>", collect_selections)
				map("n", "<CR>", collect_selections)

				return true
			end,
		})
		:find()

	-- Return the selected files (this will be populated after the picker closes)
	return selected_files
end

-- Export functions / modules from private bb_utils._*.lua modules.
M.snip = require("bb_utils._snip_utils")
M.superlazy = require("bb_utils._superlazy").superlazy
M.telescope_command_files = require("bb_utils._telescope_files")

return M
