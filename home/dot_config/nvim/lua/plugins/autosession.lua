-- Convert the cwd to a simple file name
local function get_cwd_as_name()
	local dir = vim.fn.getcwd(0)
	return dir:gsub("[^A-Za-z0-9]", "_")
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
			vim.keymap.set("n", "<leader>asl", "<cmd>Autosession search<cr>", { desc = "Search for session to load." })

			-- KEYMAP: <leader>ass
			vim.keymap.set("n", "<leader>ass", "<cmd>SessionSave<cr>", { desc = "Save session for CWD." })
		end,
	},
}
