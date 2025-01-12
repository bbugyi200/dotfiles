-- P1: Sort by priority and focus Trouble window when using ,tx map!
return {
	"folke/todo-comments.nvim",
	opts = {
		colors = {
			red = { "#ff0000" },
			orange = { "#FF8700" },
			yellow = { "#D7AF00" },
			green = { "#00AF00" },
			grey = { "#D0D0D0" },
		},
		keywords = {
			P0 = {
				icon = " ",
				color = "red",
			},
			P1 = {
				icon = " ",
				color = "orange",
			},
			P2 = {
				icon = " ",
				color = "yellow",
			},
			P3 = {
				icon = " ",
				color = "green",
			},
			X0 = {
				icon = " ",
				color = "grey",
			},
			X1 = {
				icon = " ",
				color = "grey",
			},
			X2 = {
				icon = " ",
				color = "grey",
			},
			X3 = {
				icon = " ",
				color = "grey",
			},
		},
		merge_keywords = false,
		highlight = {
			multiline_pattern = [[^  ]],
			before = "", -- "fg" or "bg" or empty
			keyword = "bg", -- "fg", "bg", "wide" or empty. (wide is the same as bg, but will also highlight surrounding characters)
			after = "fg", -- "fg" or "bg" or empty
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
		},
	},
	init = function()
		vim.keymap.set("n", "]t", function()
			require("todo-comments").jump_next()
		end, { desc = "Next todo comment" })

		vim.keymap.set("n", "[t", function()
			require("todo-comments").jump_prev()
		end, { desc = "Previous todo comment" })

		vim.keymap.set(
			"n",
			"<leader>tt",
			"<cmd>TodoTelescope<cr>",
			{ desc = "Use telescope to select a TODO to jump to." }
		)
		vim.keymap.set("n", "<leader>tx", "<cmd>TodoTrouble<cr>", { desc = "Add TODOs to Trouble panel." })
	end,
}
