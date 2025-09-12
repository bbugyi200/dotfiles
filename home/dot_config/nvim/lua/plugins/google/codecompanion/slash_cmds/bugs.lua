--- CodeCompanion /bugs slash command.
---
--- Allows users to query bugs using the `bug_show` script. These bugs are then
--- saved to a file and that file is added to the chat context.

return {
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
			local output_file = bugs_dir .. "/bug_" .. timestamp .. ".md"

			-- Run bug_show script with the query
			local cmd = { vim.env.HOME .. "/bin/bug_show", query }
			---@diagnostic disable-next-line: missing-fields
			local job = require("plenary.job"):new({
				command = cmd[1],
				args = { cmd[2] },
				on_exit = function(j, return_val)
					if return_val == 0 then
						local stdout = j:result()
						local stderr = j:stderr_result()
						local content = table.concat(stdout, "\n")
						local stderr_content = table.concat(stderr, "\n")

						if stderr_content and stderr_content ~= "" then
							vim.notify("STDERR: " .. stderr_content, vim.log.levels.WARN)
						end

						-- Write output to file
						local file = io.open(output_file, "w")
						if file then
							file:write(content)
							file:close()

							-- Schedule the buffer operations for the main event loop
							vim.schedule(function()
								-- Add content to chat as reference
								chat:add_context({
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
}
