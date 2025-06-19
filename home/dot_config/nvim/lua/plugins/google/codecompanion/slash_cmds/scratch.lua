--- CodeCompanion /local slash command.
---
--- Allows users to select files from configured local directories
--- and add them to the chat context.

-- Configure your local directories here
local scratch_dirs = {
	vim.fn.expand("~/tmp"),
}

return {
	keymaps = {
		modes = { i = "<c-g>l", n = "gl" },
	},
	callback = function(chat)
		-- Collect all files from configured directories
		local all_files = {}

		for _, dir in ipairs(scratch_dirs) do
			if vim.fn.isdirectory(dir) == 1 then
				-- Get all files recursively from this directory
				local files = vim.fn.globpath(dir, "**/*", false, true)
				for _, file in ipairs(files) do
					if vim.fn.filereadable(file) == 1 then
						table.insert(all_files, file)
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
				prompt_title = string.format("Scratch Files (%d files)", #all_files),
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

									-- Add the file as a reference to the chat
									chat:add_reference({
										role = "user",
										content = string.format(
											"File: %s\n\n```%s\n%s\n```",
											vim.fn.fnamemodify(path, ":~"),
											vim.fn.fnamemodify(path, ":e"),
											content
										),
									}, "file", path)

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
	opts = {
		contains_code = true,
	},
}
