--- Highlight, list and search todo comments in your projects.

return {
	-- PLUGIN: http://github.com/folke/todo-comments.nvim
	{
		"folke/todo-comments.nvim",
		opts = {
			colors = {
				red = { "#ff0000" },
				orange = { "#FF8700" },
				yellow = { "#D7AF00" },
				green = { "#00AF00" },
				darkgreen = { "#009900" },
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
				P4 = {
					icon = " ",
					color = "darkgreen",
				},
				XX = {
					icon = " ",
					color = "grey",
					alt = { "X0", "X1", "X2", "X3", "X4" },
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
			-- Maps to navigate to next/prev TODO.
			vim.keymap.set("n", "]t", function()
				require("todo-comments").jump_next()
			end, { desc = "Next todo comment" })
			vim.keymap.set("n", "[t", function()
				require("todo-comments").jump_prev()
			end, { desc = "Previous todo comment" })

			-- KEYMAP(N): <leader>T
			vim.keymap.set("n", "<leader>T", "<cmd>Trouble todo<cr>", { desc = "Trouble todo" })

			-- Telescope todo_comments keymaps.
			--
			-- NOTE: The dash_dash_space variable had to be factored out to make sure
			--       that no literal strings in this file match the ':Telescope
			--       todo_comments' query.
			local dash_dash_space = "-- "
			-- KEYMAP(N): <leader>ttt
			vim.keymap.set("n", "<leader>ttt", "<cmd>TodoTelescope<cr>", { desc = "Telescope todo_comments" })
			-- KEYMAP(N): <leader>tt0
			vim.keymap.set("n", "<leader>tt0", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P0:")
			end, { desc = "Telescope todo_comments (P0 only)" })
			-- KEYMAP(N): <leader>tt1
			vim.keymap.set("n", "<leader>tt1", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P1:")
			end, { desc = "Telescope todo_comments (P1 only)" })
			-- KEYMAP(N): <leader>tt2
			vim.keymap.set("n", "<leader>tt2", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P2:")
			end, { desc = "Telescope todo_comments (P2 only)" })
			-- KEYMAP(N): <leader>tt3
			vim.keymap.set("n", "<leader>tt3", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P3:")
			end, { desc = "Telescope todo_comments (P3 only)" })
			-- KEYMAP(N): <leader>tt4
			vim.keymap.set("n", "<leader>tt4", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P4:")
			end, { desc = "Telescope todo_comments (P4 only)" })
		end,
	},
}
