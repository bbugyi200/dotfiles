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
			allowed_dirs = nil, -- Allow session restore/create in certain directories
			args_allow_files_auto_save = false, -- Allow saving a session even when launched with a file argument (or multiple files/dirs). It does not load any existing session first. While you can just set this to true, you probably want to set it to a function that decides when to save a session when launched with file args. See documentation for more detail
			args_allow_single_directory = true, -- Follow normal sesion save/load logic if launched with a single directory as the only argument
			auto_create = true, -- Enables/disables auto creating new session files. Can take a function that should return true/false if a new session file should be created or not
			auto_restore = true, -- Enables/disables auto restoring session on start
			auto_restore_last_session = false, -- On startup, loads the last saved session if session for cwd does not exist
			auto_save = true, -- Enables/disables auto saving session on exit
			bypass_save_filetypes = nil, -- List of filetypes to bypass auto save when the only buffer open is one of the file types listed, useful to ignore dashboards
			close_unsupported_windows = true, -- Close windows that aren't backed by normal file before autosaving a session
			continue_restore_on_error = true, -- Keep loading the session even if there's an error
			cwd_change_handling = false, -- Follow cwd changes, saving a session before change and restoring after
			enabled = true, -- Enables/disables auto creating, saving and restoring
			lazy_support = true, -- Automatically detect if Lazy.nvim is being used and wait until Lazy is done to make sure session is restored correctly. Can be disabled if a problem is suspected or for debugging
			log_level = "error", -- Sets the log level of the plugin (debug, info, warn, error).
			lsp_stop_on_restore = false, -- Should language servers be stopped when restoring a session. Can also be a function that will be called if set. Not called on autorestore from startup
			pre_save_cmds = { "ScopeSaveState" },
			post_restore_cmds = { "ScopeLoadState" },
			root_dir = vim.fn.stdpath("data") .. "/sessions/", -- Root dir where sessions will be stored
			session_lens = {
				load_on_setup = true, -- Initialize on startup (requires Telescope)
				previewer = false, -- File preview for session picker
				mappings = {
					-- Mode can be a string or a table, e.g. {"i", "n"} for both insert and normal mode
					delete_session = { "i", "<C-D>" },
					alternate_session = { "i", "<C-S>" },
					copy_session = { "i", "<C-Y>" },
				},
				session_control = {
					control_dir = vim.fn.stdpath("data") .. "/auto_session/", -- Auto session control dir, for control files, like alternating between two sessions with session-lens
					control_filename = "session_control.json", -- File name of the session control file
				},
			},
			show_auto_restore_notif = false, -- Whether to show a notification when auto-restoring
			suppressed_dirs = nil, -- Suppress session restore/create in certain directories
			use_git_branch = false, -- Include git branch name in session name
		},
		init = function()
			vim.opt.sessionoptions =
				-- scope.nvim requires the following: buffers, globals, tabpages
				"blank,buffers,curdir,folds,globals,help,tabpages,winsize,winpos,terminal,localoptions"

			-- KEYMAP(N): <leader>as
			vim.keymap.set(
				"n",
				"<leader>as",
				"<cmd>SessionSave<cr><cmd>x<cr>",
				{ desc = "Save session and close vim." }
			)
		end,
	},
}
