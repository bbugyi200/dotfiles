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
	bugs = {
		keymaps = {
			modes = { i = "<c-g>b", n = "gB" },
		},
		callback = function(chat)
			-- Prompt user for bug query
			vim.ui.input({
				prompt = "Bug query: ",
				default = "",
			}, function(query)
				if not query or query == "" then
					vim.notify("No query provided", vim.log.levels.WARN)
					return
				end

				-- Create bugs directory if it doesn't exist
				local bugs_dir = vim.fn.expand("~/.local/share/nvim/codecompanion/bugs")
				vim.fn.mkdir(bugs_dir, "p")

				-- Generate timestamp in YYMMDD_HHMMSS format
				local timestamp = os.date("%y%m%d_%H%M%S")
				local output_file = bugs_dir .. "/bug_" .. timestamp .. ".txt"

				-- Run bug_show script with the query
				local cmd = { "bug_show", query }
				---@diagnostic disable-next-line: missing-fields
				local job = require("plenary.job"):new({
					command = cmd[1],
					args = { cmd[2] },
					on_exit = function(j, return_val)
						if return_val == 0 then
							local stdout = j:result()
							local content = table.concat(stdout, "\n")

							-- Write output to file
							local file = io.open(output_file, "w")
							if file then
								file:write(content)
								file:close()

								-- Schedule the buffer operations for the main event loop
								vim.schedule(function()
									-- Add content to chat as reference
									chat:add_reference({
										role = "user",
										content = string.format("Bug Query: %s\n\n```\n%s\n```", query, content),
									}, "bug", output_file)

									vim.notify("Bug query results saved to " .. output_file .. " and added to chat")
								end)
							else
								vim.schedule(function()
									vim.notify("Failed to write to " .. output_file, vim.log.levels.ERROR)
								end)
							end
						else
							local stderr = j:stderr_result()
							local error_msg = table.concat(stderr, "\n")
							vim.schedule(function()
								vim.notify("bug_show command failed: " .. error_msg, vim.log.levels.ERROR)
							end)
						end
					end,
				})

				job:start()
			end)
		end,
		description = "Query bugs using bug_show script and save results",
		opts = {
			contains_code = false,
		},
	},
}
