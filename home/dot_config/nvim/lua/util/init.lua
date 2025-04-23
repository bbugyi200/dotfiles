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

return M
