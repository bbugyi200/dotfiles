--- CodeCompanion /clfiles slash command.
---
--- Allows users to seleect files that are output from the `clfiles` command
--- and add them to the chat context.

local shared = require("plugins.codecompanion.slash_cmds.shared")

return {
	keymaps = {
		modes = { i = "<c-g>cL", n = "gcL" },
	},
	callback = function(chat)
		-- Prompt user for clfiles query
		vim.ui.input({
			prompt = "Clfiles query: ",
			default = "",
		}, function(query)
			if not query or query == "" then
				vim.notify("No query provided", vim.log.levels.WARN)
				return
			end

			-- Use shared utility to run command and process files
			shared.run_command_and_process_files("clfiles", { query }, chat, "clfiles", {
				title = "Clfiles Results",
				process_output = function(stdout)
					local files = {}
					for _, line in ipairs(stdout) do
						local trimmed = vim.trim(line)
						if trimmed ~= "" and vim.fn.filereadable(trimmed) == 1 then
							table.insert(files, trimmed)
						end
					end
					return files
				end,
				picker_options = {
					show_preview = false,
					entry_maker = function(entry)
						return {
							value = entry,
							display = vim.fn.fnamemodify(entry, ":."),
							ordinal = vim.fn.fnamemodify(entry, ":."),
							path = entry,
						}
					end,
				},
			})
		end)
	end,
	description = "Query files using clfiles command and add selected files to context",
	opts = {
		contains_code = true,
	},
}
