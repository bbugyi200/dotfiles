--- CodeCompanion /local slash command.
---
--- Allows users to select files from configured local directories
--- and add them to the chat context.

local fav_dirs = { vim.fn.expand("~/tmp"), vim.fn.getcwd() }
local allowed_exts = { "json", "md", "sql", "txt", "xml" }
local excluded_dirs = { vim.fn.expand("~/tmp/build/"), vim.fn.expand("~/tmp/chezmoi_build/") }

return {
	keymaps = {
		modes = { i = "<c-f>", n = "gf" },
	},
	callback = function(chat)
		-- Collect all files from configured directories
		local all_files = {}

		for _, dir in ipairs(fav_dirs) do
			if vim.fn.isdirectory(dir) == 1 then
				-- Get files from this directory (recursive for all except current working directory)
				local pattern = (dir == vim.fn.getcwd()) and "*" or "**/*"
				local files = vim.fn.globpath(dir, pattern, false, true)
				for _, file in ipairs(files) do
					if vim.fn.filereadable(file) == 1 then
						-- Check if file is in an excluded directory
						local is_excluded = false
						for _, excluded_dir in ipairs(excluded_dirs) do
							if vim.startswith(file, excluded_dir) then
								is_excluded = true
								break
							end
						end

						if is_excluded then
							goto continue
						end

						-- Check if file has an allowed extension
						local ext = vim.fn.fnamemodify(file, ":e")
						local has_allowed_ext = false
						for _, allowed_ext in ipairs(allowed_exts) do
							if ext == allowed_ext then
								has_allowed_ext = true
								break
							end
						end

						if has_allowed_ext then
							table.insert(all_files, file)
						end
						::continue::
					end
				end
			end
		end

		if #all_files == 0 then
			vim.notify("No readable files found in configured directories", vim.log.levels.WARN)
			return
		end

		-- Use telescope for file selection with multi-select capability
		local pickers = require("telescope.pickers")
		local finders = require("telescope.finders")
		local conf = require("telescope.config").values
		local actions = require("telescope.actions")
		local action_state = require("telescope.actions.state")

		pickers
			.new({}, {
				prompt_title = string.format("Favorite Files (%d files)", #all_files),
				finder = finders.new_table({
					results = all_files,
					entry_maker = function(entry)
						return {
							value = entry,
							display = vim.fn.fnamemodify(entry, ":~"),
							ordinal = vim.fn.fnamemodify(entry, ":~"),
							path = entry,
						}
					end,
				}),
				sorter = conf.file_sorter({}),
				previewer = conf.file_previewer({}),
				attach_mappings = function(prompt_bufnr, map)
					actions.select_default:replace(function()
						local picker = action_state.get_current_picker(prompt_bufnr)
						local multi_selection = picker:get_multi_selection()
						local paths = {}

						-- Handle multi-selection first
						if #multi_selection > 0 then
							for _, entry in ipairs(multi_selection) do
								table.insert(paths, entry.value)
							end
						else
							-- Single selection fallback
							local selection = action_state.get_selected_entry()
							if selection then
								table.insert(paths, selection.value)
							end
						end

						actions.close(prompt_bufnr)

						if #paths > 0 then
							-- Add each file to the chat context
							for _, path in ipairs(paths) do
								if vim.fn.filereadable(path) == 1 then
									-- Read the file content
									local content = table.concat(vim.fn.readfile(path), "\n")

									-- Add the file as a message to the chat (similar to built-in /file command)
									local relative_path = vim.fn.fnamemodify(path, ":~")
									local ft = vim.fn.fnamemodify(path, ":e")
									local id = "<file>" .. relative_path .. "</file>"

									chat:add_message({
										role = "user",
										content = string.format(
											"Here is the content from a file (including line numbers):\n```%s\n%s:%s\n%s\n```",
											ft,
											relative_path,
											relative_path,
											content
										),
									}, {
										path = path,
										context_id = id,
										tag = "file",
										visible = false,
									})

									-- Add to context tracking
									chat.context:add({
										id = id,
										path = path,
										source = "codecompanion.strategies.chat.slash_commands.favs",
									})

									vim.notify("Added " .. vim.fn.fnamemodify(path, ":~") .. " to chat context")
								else
									vim.notify("File not readable: " .. path, vim.log.levels.WARN)
								end
							end
						else
							vim.notify("No files selected", vim.log.levels.WARN)
						end
					end)

					-- Allow multi-select with Tab
					map("i", "<Tab>", actions.toggle_selection + actions.move_selection_worse)
					map("n", "<Tab>", actions.toggle_selection + actions.move_selection_worse)
					map("i", "<S-Tab>", actions.toggle_selection + actions.move_selection_better)
					map("n", "<S-Tab>", actions.toggle_selection + actions.move_selection_better)

					return true
				end,
			})
			:find()
	end,
	description = "Add files from configured local directories to context",
}
