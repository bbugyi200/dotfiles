return {
	"folke/todo-comments.nvim",
	opts = {
		highlight = {
			multiline_pattern = [[^  ]],
			before = "", -- "fg" or "bg" or empty
			keyword = "bg", -- "fg", "bg", "wide" or empty. (wide is the same as bg, but will also highlight surrounding characters)
			after = "fg", -- "fg" or "bg" or empty
			pattern = [[.*\s((KEYWORDS)%(\(bbugyi(200)?\))):]],
			comments_only = true, -- uses treesitter to match keywords in comments only
			max_line_len = 400, -- ignore lines longer than this
			exclude = {}, -- list of file types to exclude highlighting
		},
		search = {
			command = "rg",
			args = {
				"--glob=!*.snippets",
				"--color=never",
				"--no-heading",
				"--with-filename",
				"--line-number",
				"--column",
			},
			pattern = [[\s(KEYWORDS)(\(bbugyi(200)?\)):]],
		},
	},
	init = function()
		vim.keymap.set("n", "]t", function()
			require("todo-comments").jump_next()
		end, { desc = "Next todo comment" })

		vim.keymap.set("n", "[t", function()
			require("todo-comments").jump_prev()
		end, { desc = "Previous todo comment" })

		vim.keymap.set("n", "<leader>T", "<cmd>TodoTelescope<cr>", { desc = "Previous todo comment" })
	end,
}
