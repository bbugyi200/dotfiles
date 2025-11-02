--- CodeCompanion /xref slash command.
---
--- Allows users to find references to a symbol using the xref_files script.
--- The symbol can be provided as input or defaults to clipboard contents.
--- All files containing references to the symbol are added to the chat context.

local shared = require("plugins.codecompanion.slash_cmds.shared")

return {
	keymaps = {
		modes = { i = "<c-g>xr", n = "gxr" },
	},
	---@diagnostic disable-next-line: undefined-doc-name
	---@param chat CodeCompanion.Chat
	callback = function(chat)
		-- Check if xref_files command exists
		if vim.fn.executable("xref_files") ~= 1 then
			vim.notify("xref_files command not found in PATH", vim.log.levels.ERROR)
			return
		end

		-- Show current clipboard contents as notification
		local clipboard_content = shared.get_clipboard_contents()

		if clipboard_content and vim.trim(clipboard_content) ~= "" then
			-- Truncate long clipboard content for notification
			local display_content = clipboard_content
			if #display_content > 100 then
				display_content = display_content:sub(1, 100) .. "..."
			end
			-- Remove newlines for cleaner notification
			display_content = display_content:gsub("\n", " ")

			vim.notify("CLIPBOARD: " .. display_content, vim.log.levels.INFO, { title = "XRefs" })
		else
			vim.notify("Clipboard is empty!", vim.log.levels.WARN, { title = "XRefs" })
			return
		end

		-- Use shared utility to run command and process files
		shared.run_command_and_process_files("xref_files", {}, chat, "xrefs", {
			title = "XRef Files",
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
				show_preview = true,
			},
		})
	end,
	description = "Find files using xref_files and select which to add to context",
	opts = {
		contains_code = true,
	},
}
