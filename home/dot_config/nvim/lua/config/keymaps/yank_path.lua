--- Keymaps that are used to yank parts of the current file's path to our system clipboard.

local copy_to_clipboard = require("util.copy_to_clipboard")

--- Yank basename of current file.
---
---@param strip_ext? boolean Whether to strip the file extension.
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

--- Yank absolute file path.
---
---@param use_tilde boolean Whether to use a tilde for the home directory.
local function yank_absolute_path(use_tilde)
	local absolute_path = vim.fn.expand("%:p")
	if use_tilde then
		absolute_path = vim.fn.fnamemodify(absolute_path, ":~")
	end
	copy_to_clipboard(absolute_path)
end

--- Yank file path relative to current working directory.
local function yank_relative_path()
	local relative_path = vim.fn.expand("%")
	copy_to_clipboard(relative_path)
end

-- KEYMAP GROUP: <leader>y
vim.keymap.set("n", "<leader>y", "<nop>", { desc = "Yank Path" })

-- KEYMAP: ya
vim.keymap.set("n", "<leader>ya", function()
	yank_absolute_path(true)
end, {
	desc = "Yank this file's absolute path (use ~ for home dir).",
})

-- KEYMAP: yA
vim.keymap.set("n", "<leader>yA", yank_absolute_path, {
	desc = "Yank this file's absolute path.",
})

-- KEYMAP: <leader>yb
vim.keymap.set("n", "<leader>yb", yank_basename, {
	desc = "Yank this file's basename (including ext).",
})

-- KEYMAP: <leader>yB
vim.keymap.set("n", "<leader>yB", function()
	yank_basename(true)
end, { desc = "Yank this file's basename (excluding extension)." })

-- KEYMAP: <leader>yd
vim.keymap.set("n", "<leader>yd", yank_directory, { desc = "Yank this file's parent directory." })

-- KEYMAP: yr
vim.keymap.set("n", "<leader>yr", yank_relative_path, {
	desc = "Yank this file's full path relative to the CWD.",
})
