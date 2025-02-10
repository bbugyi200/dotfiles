--- Keymaps that are used to yank parts of the current file's path to our system clipboard.

local copy_to_clipboard = require("util.copy_to_clipboard").copy_to_clipboard

--- Yank basename of current file.
---
---@param strip_ext boolean Whether to strip the file extension.
local function yank_basename(strip_ext)
	local format_str = "%:t"
	if strip_ext then
		format_str = format_str .. ":r"
	end
	copy_to_clipboard(vim.fn.expand(format_str))
end

--- Yank directory path relative to current working directory.
local function yank_directory()
	-- Get absolute path of current buffer's file
	local absolute_path = vim.fn.expand("%:p")
	-- Get directory path
	local directory_path = vim.fn.fnamemodify(absolute_path, ":h")
	-- Get current working directory
	local cwd = vim.fn.getcwd()
	-- Remove cwd from the directory path
	local stripped_directory_path = directory_path:gsub("^" .. vim.pesc(cwd) .. "/", "")
	-- Copy to clipboard
	copy_to_clipboard(stripped_directory_path)
end

--- Yank file path relative to current working directory.
local function yank_relative_path()
	local cwd = vim.fn.getcwd()
	local full_path = vim.fn.expand("%")
	local relative_path = full_path:gsub("^" .. vim.pesc(cwd) .. "/", "")
	copy_to_clipboard(relative_path)
end

-- KEYMAP(N): <leader>yb
vim.keymap.set("n", "<leader>yb", yank_basename, {
	desc = "Yank this file's basename (including ext).",
})

-- KEYMAP(N): <leader>yB
vim.keymap.set("n", "<leader>yB", function()
	yank_basename(true)
end, { desc = "Yank this file's basename (excluding extension)." })

-- KEYMAP(N): <leader>yd
vim.keymap.set("n", "<leader>yd", yank_directory, { desc = "Yank this file's parent directory." })

-- KEYMAP(N): yp
vim.keymap.set("n", "<leader>yp", yank_relative_path, {
	desc = "Yank this file's full path relative to the CWD.",
})
