--- Creates a keymap that is repeatable via the `.` command.
---
---@param name string A unique name for the intermediate <Plug> mapping.
---@param lhs string The left-hand side of the keymap.
---@param rhs string The right-hand side of the keymap.
---@param opts table<string, any> The description of the keymap.
local function repeat_keymap(name, lhs, rhs, opts)
	-- map unique Plug mapping using tostring of function
	local plug_lhs = "<Plug>" .. name
	-- mapping including vim-repeat magic
	local repeat_rhs = plug_lhs .. [[:silent! call repeat#set("\]] .. plug_lhs .. [[", v:count)<CR>]]
	vim.keymap.set("n", plug_lhs, rhs)
	vim.keymap.set("n", lhs, repeat_rhs, opts)
end

return repeat_keymap
