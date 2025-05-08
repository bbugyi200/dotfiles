--- Highlight, list and search todo comments in your projects.

--- Find the common parent directory of all currently open buffers.
---
--- This function examines the file paths of all open buffers and determines
--- the most specific common parent directory that contains all of them.
---
--- @return string|nil # The common parent directory path, or nil if no common directory exists

return {
	-- PLUGIN: http://github.com/folke/todo-comments.nvim
	{
		"folke/todo-comments.nvim",
		opts = {
			colors = {
				very_high_priority = { "DiagnosticError" },
				high_priority = { "#FF8700" },
				medium_priority = { "#D7AF00" },
				low_priority = { "#00AF00" },
				very_low_priority = { "#009900" },
			},
			keywords = {
				P0 = {
					icon = "🚨",
					color = "very_high_priority",
					alt = { "TODO" },
				},
				P1 = {
					icon = "⚠️",
					color = "high_priority",
				},
				P2 = {
					icon = "⭐",
					color = "medium_priority",
				},
				P3 = {
					icon = "✅",
					color = "low_priority",
				},
				P4 = {
					icon = "☑️",
					color = "very_low_priority",
				},
			},
			merge_keywords = false,
			highlight = {
				pattern = [[.*<((KEYWORDS)%(\(bbugyi\))?):]],
				multiline_pattern = [[^  ]],
				-- "fg" or "bg" or empty
				before = "",
				-- "fg", "bg", "wide" or empty. (wide is the same as bg, but will also highlight surrounding characters)
				keyword = "bg",
				-- "fg" or "bg" or empty
				after = "fg",
				-- uses treesitter to match keywords in comments only
				comments_only = true,
				-- ignore lines longer than this
				max_line_len = 400,
				-- list of file types to exclude highlighting
				exclude = {},
			},
			search = {
				pattern = [[\b(KEYWORDS)(\(bbugyi\))?:]],
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
			vim.keymap.set("n", "]T", function()
				require("todo-comments").jump_next()
			end, { desc = "Next todo comment" })
			vim.keymap.set("n", "[T", function()
				require("todo-comments").jump_prev()
			end, { desc = "Previous todo comment" })

			-- KEYMAP: <leader>T
			vim.keymap.set("n", "<leader>T", "<cmd>Trouble todo<cr>", { desc = "Trouble todo" })

			-- ────────────────── Telescope todo_comments keymaps. ───────────────
			-- KEYMAP GROUP: <leader>tt
			vim.keymap.set("n", "<leader>tt", "<nop>", { desc = "Telescope todo_comments" })

			-- NOTE: The dash_dash_space variable had to be factored out to make sure
			--       that no literal strings in this file match the ':Telescope
			--       todo_comments' query.
			--
			-- P2: De-duplicate <leader>tt0-4 keymaps?!
			local dash_dash_space = "-- "
			-- KEYMAP: <leader>ttt
			vim.keymap.set("n", "<leader>ttt", "<cmd>TodoTelescope<cr>", { desc = "Telescope todo_comments" })
			-- KEYMAP: <leader>tt0
			vim.keymap.set("n", "<leader>tt0", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P0:")
			end, { desc = "TodoTelescope (P0 only)" })
			-- KEYMAP: <leader>tt1
			vim.keymap.set("n", "<leader>tt1", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P1:")
			end, { desc = "TodoTelescope (P1 only)" })
			-- KEYMAP: <leader>tt2
			vim.keymap.set("n", "<leader>tt2", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P2:")
			end, { desc = "TodoTelescope (P2 only)" })
			-- KEYMAP: <leader>tt3
			vim.keymap.set("n", "<leader>tt3", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P3:")
			end, { desc = "TodoTelescope (P3 only)" })
			-- KEYMAP: <leader>tt4
			vim.keymap.set("n", "<leader>tt4", function()
				vim.cmd("TodoTelescope")
				vim.fn.feedkeys(dash_dash_space .. "P4:")
			end, { desc = "TodoTelescope (P4 only)" })
		end,
	},
}
