--- Neovim utility functions live here!
--
-- P0: Migrate all other utility functions to this file / package!

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
		notify_cmd_failed(command_name)

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
	if altfile ~= "" and vim.fn.filereadable(altfile) then
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

	if close_window_if_multiple and #vim.api.nvim_list_wins() > 1 then
		vim.cmd("wincmd c")
	end
end

return M
