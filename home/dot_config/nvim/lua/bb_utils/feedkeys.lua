--- Wrapper around `vim.api.nvim_feedkeys()`.
---
---@param keys string The keys to type in normal mode.
local function feedkeys(keys)
	vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(keys, true, true, true), "n", true)
end

return feedkeys

