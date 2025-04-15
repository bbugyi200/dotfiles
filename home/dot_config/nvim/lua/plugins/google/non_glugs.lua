return {
	-- Provides :TransformCode command that lets LLMs modify current file/selection.
	--
	-- See http://google3/experimental/users/vvvv/ai.nvim.
	{
		url = "sso://user/vvvv/ai.nvim",
		dependencies = {
			"nvim-lua/plenary.nvim",
		},
		cmd = "TransformCode",
		keys = {
			{ "<leader>tc", "<cmd>TransformCode<cr>", mode = { "n", "v" }, desc = "Transform code" },
		},
	},
	-- Load google paths like //google/* when opening files.
	-- Also works with `gf`, although in mosts cases,
	-- running `vim.lsp.buf.definition()` (by default mapped to `gd`)
	-- over a path will also take you to the file
	--
	-- See http://google3/experimental/users/fentanes/googlepaths.nvim
	{
		url = "sso://user/fentanes/googlepaths.nvim",
		event = { #vim.fn.argv() > 0 and "VeryLazy" or "UIEnter", "BufReadCmd //*", "BufReadCmd google3/*" },
		opts = {},
	},
	-- Add autocomplete when typing b/, BUG=, and FIXED=
	--
	-- See go/cmp-buganizer
	{
		url = "sso://user/vicentecaycedo/cmp-buganizer",
		cond = function()
			return vim.fn.executable("bugged") == 1
		end,
		config = function(_, opts)
			local cmp_buganizer = require("cmp-buganizer")
			cmp_buganizer.setup(opts)
		end,
		opts = {},
	},
	-- Show comments from critique
	-- go/google-comments-nvim
	{
		url = "sso://user/chmnchiang/google-comments",
		dependencies = {
			"nvim-lua/plenary.nvim",
		},
		main = "google.comments",
		opts = {
			display = {
				floating = true,
			},
		},
		keys = {
			{
				"[lc",
				"<cmd>lua require('google.comments').goto_prev_comment()<cr>",
				desc = "Goto previous comment",
			},
			{
				"]lc",
				"<cmd>lua require('google.comments').goto_next_comment()<cr>",
				desc = "Goto next comment",
			},
			{
				"<leader>lc",
				"<cmd>lua require('google.comments').toggle_line_comments()<cr>",
				desc = "Toggle line comments",
			},
			{
				"<leader>ac",
				"<cmd>lua require('google.comments').show_all_comments()<cr>",
				desc = "Show all comments",
			},
		},
	},
	-- Create new piper and fig workspaces
	-- go/neocitc
	{
		url = "sso://team/neovim-dev/neocitc",
		branch = "main",
		cmd = { "CitcCreateFigWorkspace" },
		keys = {
			{
				"<leader>cf",
				":CitcCreateFigWorkspace ",
				desc = "Create new citc fig workspace",
			},
		},
	},
	-- Display and search for buganizer bugs
	-- go/buganizer.nvim
	{
		url = "sso://user/rprs/buganizer.nvim",
		dependencies = {
			"nvim-telescope/telescope.nvim",
			{ url = "sso://user/vicentecaycedo/buganizer-utils.nvim" },
		},
		init = function()
			-- KEYMAP GROUP: <leader>bu
			vim.keymap.set("n", "<leader>bu", "<nop>", { desc = "buganizer.nvim" })

			-- KEYMAP: <leader>buf
			vim.keymap.set("n", "<leader>buf", "<cmd>FindBugs<cr>", { desc = "Find bugs." })

			-- KEYMAP: <leader>bui
			vim.keymap.set("n", "<leader>bui", "<cmd>BuganizerSearch<cr>", { desc = "Insert bug ID." })

			-- KEYMAP: <leader>bus
			vim.keymap.set("n", "<leader>bus", "<cmd>ShowBugUnderCursor<cr>", { desc = "Show bug under cursor." })
		end,
	},
	-- PLUGIN: http://go/critique-nvim
	{
		name = "critique-nvim",
		url = "sso://googler@user/cnieves/critique-nvim",
		main = "critique.comments",
		dependencies = {
			"rktjmp/time-ago.vim",
			"nvim-lua/plenary.nvim",
			"nvim-telescope/telescope.nvim",
			"runiq/neovim-throttle-debounce",
		},
		opts = {},
		init = function()
			-- KEYMAP GROUP: <leader>cr
			vim.keymap.set("n", "<leader>cr", "<nop>", { desc = "critique.nvim" })
		end,
	},
}
