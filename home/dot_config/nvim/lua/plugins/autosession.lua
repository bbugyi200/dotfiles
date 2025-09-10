local bb = require("bb_utils")

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
			args_allow_files_auto_save = true,
			args_allow_single_directory = true,
			auto_create = false,
			auto_restore = true,
			auto_restore_last_session = false,
			auto_save = true,
			close_unsupported_windows = true,
			continue_restore_on_error = true,
			cwd_change_handling = false,
			enabled = true,
			git_use_branch_name = false,
			lazy_support = true,
			log_level = "error",
			lsp_stop_on_restore = false,
			post_restore_cmds = { "ScopeLoadState" },
			pre_save_cmds = { "ScopeSaveState" },
			root_dir = "/Users/bbugyi/.local/share/nvim/sessions/",
			session_lens = {
				load_on_setup = true,
				mappings = {
					alternate_session = { "i", "<C-S>" },
					copy_session = { "i", "<C-Y>" },
					delete_session = { "i", "<C-D>" },
				},
				previewer = false,
				session_control = {
					control_dir = "/Users/bbugyi/.local/share/nvim/auto_session/",
					control_filename = "session_control.json",
				},
			},
			show_auto_restore_notif = false,
		},
		init = function()
			vim.opt.sessionoptions =
				-- scope.nvim requires the following: buffers, globals, tabpages
				"blank,buffers,curdir,folds,globals,help,tabpages,winsize,winpos,terminal,localoptions"

			-- KEYMAP GROUP: <leader>as
			vim.keymap.set("n", "<leader>as", "<nop>", { desc = "autosession.nvim" })

			-- KEYMAP: <leader>asd
			vim.keymap.set(
				"n",
				"<leader>asd",
				"<cmd>AutoSession delete " .. bb.get_default_session_name() .. "<cr>",
				{ desc = "Delete current session." }
			)

			-- KEYMAP: <leader>asD
			vim.keymap.set("n", "<leader>asD", ":AutoSession delete ", {
				desc = "Delete session with custom name.",
			})

			-- KEYMAP: <leader>asl
			vim.keymap.set("n", "<leader>asl", function()
				vim.cmd("AutoSession restore " .. bb.get_default_session_name())
			end, { desc = "Load session for CWD." })

			-- KEYMAP: <leader>asL
			vim.keymap.set("n", "<leader>asL", "<cmd>Autosession search<cr>", { desc = "Search for session to load." })

			-- KEYMAP: <leader>ass
			vim.keymap.set("n", "<leader>ass", function()
				vim.cmd("AutoSession save " .. bb.get_default_session_name())
			end, { desc = "Save session for CWD." })

			-- KEYMAP: <leader>asS
			vim.keymap.set("n", "<leader>asS", ":AutoSession save ", { desc = "Save session with custom name." })
		end,
	},
}
