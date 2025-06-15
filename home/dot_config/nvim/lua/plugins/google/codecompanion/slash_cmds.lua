return {
	cs = {
		keymaps = {
			modes = { i = "<c-c>", n = "gc" },
		},
		callback = function(chat)
			-- Check if telescope-codesearch is available
			local telescope = require("telescope")
			if not telescope.extensions.codesearch then
				vim.notify("telescope-codesearch extension not found", vim.log.levels.ERROR)
				return
			end
			local picker_opts = {
				attach_mappings = function(prompt_bufnr, map)
					local actions = require("telescope.actions")
					local action_state = require("telescope.actions.state")

					actions.select_default:replace(function()
						local picker = action_state.get_current_picker(prompt_bufnr)
						local multi_selection = picker:get_multi_selection()
						local paths = {}

						-- Handle multi-selection first
						if #multi_selection > 0 then
							for _, entry in ipairs(multi_selection) do
								local path = entry.value or entry.path or entry.filename
								if path then
									table.insert(paths, path)
								end
							end
						else
							-- Single selection fallback
							local selection = action_state.get_selected_entry()
							if selection then
								local path = selection.value or selection.path or selection.filename
								if path then
									table.insert(paths, path)
								end
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
											vim.fn.fnamemodify(path, ":."),
											vim.fn.fnamemodify(path, ":e"),
											content
										),
									}, "file", path)

									vim.notify("Added " .. vim.fn.fnamemodify(path, ":.") .. " to chat context")
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
				-- Add some useful codesearch options
				experimental = true, -- Include experimental directory
				enable_proximity = true, -- Enable proximity search
				max_num_results = 100, -- Increase max results
			}

			telescope.extensions.codesearch.find_query(picker_opts)
		end,
		description = "Add files from CodeSearch to context",
		opts = {
			contains_code = true,
		},
	},
}
