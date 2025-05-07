--- Highlight, list and search todo comments in your projects.

--- Find the common parent directory of all currently open buffers.
---
--- This function examines the file paths of all open buffers and determines
--- the most specific common parent directory that contains all of them.
---
--- @return string|nil # The common parent directory path, or nil if no common directory exists
local function get_common_parent_dir()
	-- Get a list of all buffer handles
	local buffers = vim.api.nvim_list_bufs()
	local paths = {}

	-- Collect non-empty file paths from all buffers
	for _, buf in ipairs(buffers) do
		local filename = vim.api.nvim_buf_get_name(buf)
		if filename ~= "" then
			table.insert(paths, filename)
		end
	end

	-- Handle edge cases with no or single buffer
	if #paths == 0 then
		return nil
	end
	if #paths == 1 then
		return vim.fn.fnamemodify(paths[1], ":h")
	end

	-- Helper function to split a path into its component parts
	local function split_path(path)
		local parts = {}
		for part in path:gmatch("[^/]+") do
			table.insert(parts, part)
		end
		return parts
	end

	-- Use the first path as the initial reference for common parts
	local shortest_path_parts = split_path(paths[1])
	local common_parts = {}

	-- Compare each path segment across all paths
	for i = 1, #shortest_path_parts do
		local current_part = shortest_path_parts[i]
		local is_common = true

		-- Check if this part is the same for all paths
		for j = 2, #paths do
			local other_parts = split_path(paths[j])
			if i > #other_parts or other_parts[i] ~= current_part then
				is_common = false
				break
			end
		end

		-- Stop when we find a non-common part
		if is_common then
			table.insert(common_parts, current_part)
		else
			break
		end
	end

	-- Reconstruct the common path, ensuring it starts with a root slash
	return "/" .. table.concat(common_parts, "/")
end

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
