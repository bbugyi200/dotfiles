--- Filetype: netrw
--
-- P2: Add ,y*; ,m*; and ,c* keymaps to netrw buffers?

local delete_file = require("util.delete_file")
local quit_special_buffer = require("util.quit_special_buffer")

--- Fetch the path of the file under the cursor in a netrw buffer.
---
---@return string # The absolute path of the file under the cursor in a netrw buffer.
local function get_path_of_netrw_file()
	local line = vim.fn.getline(".")
	local split_lines = vim.split(line, "%s+", { trip_empty = true })
	-- If we are using the tree view, the path is in the second column.
	if split_lines[1] == "|" then
		line = split_lines[2]
	else
		line = split_lines[1]
	end
	return vim.fs.joinpath(vim.b.netrw_curdir, line)
end

-- Remove the netrw buffer when it is hidden.
--
-- For more info on why this is useful, see:
-- https://vi.stackexchange.com/questions/14622/how-can-i-close-the-netrw-buffer
vim.bo.bufhidden = "wipe"

-- HACK: I'm not sure why 'help' buffers don't respect the global settings,
-- but they don't :/.
vim.wo.number = true
vim.wo.relativenumber = true

-- ╭─────────────────────────────────────────────────────────╮
-- │                         KEYMAPS                         │
-- ╰─────────────────────────────────────────────────────────╯
-- KEYMAP: q
vim.keymap.set("n", "q", quit_special_buffer, { buffer = true, desc = "Close the netrw window.", nowait = true })

-- KEYMAP: <tab>
vim.keymap.set("n", "<tab>", "<cmd>normal mfj<cr>", {
	desc = "Toggle mark for current file and move cursor to next file.",
})
-- KEYMAP: <s-tab>
vim.keymap.set("n", "<s-tab>", "<cmd>normal mfk<cr>", {
	desc = "Toggle mark for current file and move cursor to previous file.",
})
-- KEYMAP: D
vim.keymap.set({ "n", "v" }, "D", function()
	delete_file(get_path_of_netrw_file())
	vim.cmd("edit") -- refreshes netrw buffer so that the file is removed from the list
end, { buffer = true, desc = "Delete the file under the cursor." })
