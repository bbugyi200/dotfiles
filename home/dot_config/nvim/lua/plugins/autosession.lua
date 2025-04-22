-- Convert the cwd to a simple file name
local function get_cwd_as_name()
	local dir = vim.fn.getcwd(0)
	return dir:gsub("[^A-Za-z0-9]", "_")
end

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
local function get_session_name()
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

return {
	-- PLUGIN: http://github.com/rmagatti/auto-session
	{
		"rmagatti/auto-session",
		dependencies = {
			-- Autosession depends on the Scope*State commands (provided by
			-- scopes.nvim) used in the *_cmds hooks below!
			"tiagovla/scope.nvim",
		},
		opts = {
			-- Allow session restore/create in certain directories
			allowed_dirs = nil,
			-- Allow saving a session even when launched with a file argument (or
			-- multiple files/dirs). It does not load any existing session first.
			-- While you can just set this to true, you probably want to set it to a
			-- function that decides when to save a session when launched with file
			-- args. See documentation for more detail
			args_allow_files_auto_save = false,
			-- Follow normal sesion save/load logic if launched with a single
			-- directory as the only argument
			args_allow_single_directory = true,
			-- Enables/disables auto creating new session files. Can take a function
			-- that should return true/false if a new session file should be created
			-- or not
			auto_create = false,
			-- Enables/disables auto restoring session on start
			auto_restore = true,
			-- On startup, loads the last saved session if session for cwd does not exist
			auto_restore_last_session = false,
			-- Enables/disables auto saving session on exit
			auto_save = true,
			-- List of filetypes to bypass auto save when the only buffer open is one
			-- of the file types listed, useful to ignore dashboards
			bypass_save_filetypes = nil,
			-- Close windows that aren't backed by normal file before autosaving a session
			close_unsupported_windows = true,
			-- Keep loading the session even if there's an error
			continue_restore_on_error = true,
			-- Follow cwd changes, saving a session before change and restoring after
			cwd_change_handling = false,
			-- Enables/disables auto creating, saving and restoring
			enabled = true,
			-- Automatically detect if Lazy.nvim is being used and wait until Lazy is
			-- done to make sure session is restored correctly. Can be disabled if a
			-- problem is suspected or for debugging
			lazy_support = true,
			-- Sets the log level of the plugin (debug, info, warn, error).
			log_level = "error",
			-- Should language servers be stopped when restoring a session. Can also
			-- be a function that will be called if set. Not called on autorestore
			-- from startup
			lsp_stop_on_restore = false,
			pre_restore_cms = {
				function()
					local overseer = require("overseer")
					for _, task in ipairs(overseer.list_tasks({})) do
						task:dispose(true)
					end
				end,
			},
			pre_save_cmds = {
				"ScopeSaveState",
				function()
					local overseer = require("overseer")
					overseer.save_task_bundle(
						get_cwd_as_name(),
						-- Passing nil will use config.opts.save_task_opts. You can call list_tasks() explicitly and
						-- pass in the results if you want to save specific tasks.
						nil,
						{ on_conflict = "overwrite" } -- Overwrite existing bundle, if any
					)
				end,
			},
			post_restore_cmds = {
				"ScopeLoadState",
				function()
					local overseer = require("overseer")
					overseer.load_task_bundle(get_cwd_as_name(), { ignore_missing = true })
				end,
			},
			-- Root dir where sessions will be stored
			root_dir = vim.fn.stdpath("data") .. "/sessions/",
			session_lens = {
				-- Initialize on startup (requires Telescope)
				load_on_setup = true,
				-- File preview for session picker
				previewer = false,
				mappings = {
					-- Mode can be a string or a table, e.g. {"i", "n"} for both insert
					-- and normal mode
					delete_session = { "i", "<C-D>" },
					alternate_session = { "i", "<C-S>" },
					copy_session = { "i", "<C-Y>" },
				},
				session_control = {
					-- Auto session control dir, for control files, like alternating
					-- between two sessions with session-lens
					control_dir = vim.fn.stdpath("data") .. "/auto_session/",
					-- File name of the session control file
					control_filename = "session_control.json",
				},
			},
			-- Whether to show a notification when auto-restoring
			show_auto_restore_notif = false,
			-- Suppress session restore/create in certain directories
			suppressed_dirs = nil,
			-- Include git branch name in session name
			use_git_branch = false,
		},
		init = function()
			vim.opt.sessionoptions =
				-- scope.nvim requires the following: buffers, globals, tabpages
				"blank,buffers,curdir,folds,globals,help,tabpages,winsize,winpos,terminal,localoptions"

			-- KEYMAP GROUP: <leader>as
			vim.keymap.set("n", "<leader>as", "<nop>", { desc = "autosession.nvim" })

			-- KEYMAP: <leader>asd
			vim.keymap.set("n", "<leader>asd", "<cmd>SessionDelete<cr>", { desc = "Delete current session." })

			-- KEYMAP: <leader>asl
			vim.keymap.set("n", "<leader>asl", function()
				vim.cmd("SessionLoad " .. get_session_name())
			end, { desc = "Load session for CWD." })

			-- KEYMAP: <leader>asL
			vim.keymap.set("n", "<leader>asL", "<cmd>Autosession search<cr>", { desc = "Search for session to load." })

			-- KEYMAP: <leader>ass
			vim.keymap.set("n", "<leader>ass", function()
				vim.cmd("SessionSave " .. get_session_name())
			end, { desc = "Save session for CWD." })

			-- KEYMAP: <leader>asS
			vim.keymap.set("n", "<leader>asS", ":SessionSave ", { desc = "Save session with custom name." })
		end,
	},
}
