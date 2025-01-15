--- Source local vimrc / init.lua files.

--- Source {file}, if it exists.
---
---@param file string A *.vim or *.lua file to be sourced.
local function source_if_exists(file)
	local expanded = vim.fn.expand(file)
	if vim.fn.filereadable(expanded) == 1 then
		vim.cmd("source " .. expanded)
	end
end

source_if_exists(vim.env.HOME .. "/.vimrc.local")
