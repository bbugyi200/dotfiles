--- CodeCompanion /xpath slash command.
---
--- Allows users to copy one or more filepaths (separated by whitespace) to their clipboard
--- and adds those files to the chat context.

local shared = require("plugins.codecompanion.slash_cmds.shared")

return {
	keymaps = {
		modes = { i = "<c-g>,", n = "g," },
	},
	---@diagnostic disable-next-line: undefined-doc-name
	---@param chat CodeCompanion.Chat
	callback = function(chat)
		-- Get clipboard contents
		local input = shared.get_clipboard_contents()
		if not input then
			return
		end

		if not input or vim.trim(input) == "" then
			vim.notify("Clipboard is empty", vim.log.levels.WARN)
			return
		end

		local added_count, failed_files = shared.process_filepaths_from_string(input, chat, "xpath")

		if #failed_files == 0 and added_count == 0 then
			vim.notify("No valid filepaths found", vim.log.levels.WARN)
			return
		end

		-- Provide feedback to user
		if added_count > 0 then
			vim.notify(string.format("Added %d files to chat context", added_count), vim.log.levels.INFO)
		end

		if #failed_files > 0 then
			vim.notify(
				string.format("Failed to read %d files: %s", #failed_files, table.concat(failed_files, ", ")),
				vim.log.levels.WARN
			)
		end
	end,
	description = "Add multiple files to context from clipboard (filepaths separated by whitespace)",
	opts = {
		contains_code = true,
	},
}
