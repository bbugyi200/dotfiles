--- Helper to copy text to the system clipboard
---
---@param text string The text to copy to the clipboard.
---@param should_append? boolean Whether to append the text to the clipboard.
local function copy_to_clipboard(text, should_append)
	local msg_prefix, new_clip
	if should_append then
		msg_prefix = "APPENDED TO CLIPBOARD"
		local old_clip = vim.fn.getreg("+")
		new_clip = old_clip .. text
	else
		msg_prefix = "COPIED"
		new_clip = text
	end
	vim.fn.setreg("+", new_clip)
	vim.notify(msg_prefix .. ": " .. text)
end

return copy_to_clipboard

