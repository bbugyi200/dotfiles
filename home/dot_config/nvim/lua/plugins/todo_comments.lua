--- Highlight, list and search todo comments in your projects.

--- Find the common parent directory of all currently open buffers.
---
--- This function examines the file paths of all open buffers and determines
--- the most specific common parent directory that contains all of them.
---
--- @return string|nil # The common parent directory path, or nil if no common directory exists
local function get_common_parent_dir()
	---------------------------------------------------------------------------
	-- 1.  Collect *directory* names (absolute, real-path) of all on-disk buffers
	---------------------------------------------------------------------------
	local buffers = vim.api.nvim_list_bufs()
	local dir_parts = {} -- { { "home", "user", "proj" }, ... }

	for _, buf in ipairs(buffers) do
		local fname = vim.api.nvim_buf_get_name(buf)
		if fname ~= "" then
			-- :p   → absolute path
			-- :h   → directory (head) of the path
			local dir = vim.fn.fnamemodify(fname, ":p:h")
			dir = vim.loop.fs_realpath(dir) or dir -- resolve symlinks
			table.insert(dir_parts, vim.split(dir, "/"))
		end
	end

	---------------------------------------------------------------------------
	-- 2.  Edge cases
	---------------------------------------------------------------------------
	if #dir_parts == 0 then -- no files
		return nil
	elseif #dir_parts == 1 then -- exactly one file
		return "/" .. table.concat(dir_parts[1], "/")
	end

	---------------------------------------------------------------------------
	-- 3.  Walk segment-by-segment until there is a mismatch
	---------------------------------------------------------------------------
	local common = {}
	local max_i = math.min( -- only need to walk as far as the shortest
		table.unpack(vim.tbl_map(function(p)
			return #p
		end, dir_parts))
	)

	for i = 1, max_i do
		local candidate = dir_parts[1][i]
		for j = 2, #dir_parts do
			if dir_parts[j][i] ~= candidate then
				return #common == 0 and "/" or ("/" .. table.concat(common, "/"))
			end
		end
		table.insert(common, candidate)
	end

	return "/" .. table.concat(common, "/")
end

return {
	-- PLUGIN: http://github.com/folke/todo-comments.nvim
	{
		"folke/todo-comments.nvim",
		opts = {
			colors = {
				red = { "DiagnosticError" },
				orange = { "#FF8700" },
				yellow = { "#D7AF00" },
				green = { "#00AF00" },
				darkgreen = { "#009900" },
				grey = { "#D0D0D0" },
			},
			keywords = {
				P0 = {
					icon = "🚨",
					color = "red",
					alt = { "TODO" },
				},
				P1 = {
					icon = "⚠️",
					color = "orange",
				},
				P2 = {
					icon = "⭐",
					color = "yellow",
				},
				P3 = {
					icon = "✅",
					color = "green",
				},
				P4 = {
					icon = "☑️",
					color = "darkgreen",
				},
			},
			merge_keywords = false,
			highlight = {
				pattern = [[.*<((KEYWORDS)%(\(.{-1,}\))?):]],
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
				pattern = [[\b(KEYWORDS)(\([^\)]*\))?:]],
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
			-- KEYMAP: <leader>ttT
			vim.keymap.set("n", "<leader>ttT", function()
				local common_parent_dir = get_common_parent_dir()
				local cmd = "TodoTelescope cwd=" .. common_parent_dir
				vim.notify("RUNNING COMMAND: " .. cmd)
				vim.cmd(cmd)
			end, { desc = "TodoTelescope cwd=<COMMON_PARENT_DIR>" })
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
