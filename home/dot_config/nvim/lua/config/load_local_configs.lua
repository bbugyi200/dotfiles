--- Source local vimrc / init.lua files.
--
-- P2: Improve local vimrc
--   [x] Add autocmd for $(pwd)/.nvim.lua
--   [ ] Move ~/.vimrc.local to ~/etc/vimrc?
--   [x] Support init.lua equivalents to the above!

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

-- Source .nvim.lua from the current working directory (and re-source on :cd).
source_if_exists(vim.fn.getcwd() .. "/.nvim.lua")

vim.api.nvim_create_autocmd("DirChanged", {
	desc = "Source .nvim.lua when changing directories",
	callback = function()
		source_if_exists(vim.fn.getcwd() .. "/.nvim.lua")
	end,
})
