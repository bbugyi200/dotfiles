--- Keymaps that delete the current buffer / file live here.

local kill_buffer = require("util.kill_buffer").kill_buffer
local delete_file = require("util.delete_file")

--- Deletes all buffers to the left of the current buffer.
local function delete_buffers_to_left()
	local current_buf = vim.fn.bufnr("%")
	for bufnum = 1, current_buf - 1 do
		if vim.fn.bufexists(bufnum) == 1 and vim.fn.buflisted(bufnum) == 1 then
			vim.cmd("bdelete " .. bufnum)
		end
	end
end

--- Deletes all buffers to the right of the current buffer.
local function delete_buffers_to_right()
	local current_buf = vim.fn.bufnr("%")
	for bufnum = current_buf + 1, vim.fn.bufnr("$") do
		if vim.fn.bufexists(bufnum) == 1 and vim.fn.buflisted(bufnum) == 1 then
			vim.cmd("bdelete " .. bufnum)
		end
	end
end

-- KEYMAP GROUP: <leader>d
vim.keymap.set("n", "<leader>d", "<nop>", { desc = "Delete Buffers" })

-- KEYMAP: <leader>d<
vim.keymap.set("n", "<leader>d<", delete_buffers_to_left, {
	desc = "Delete all buffers to the left of the current buffer.",
})

-- KEYMAP: <leader>d>
vim.keymap.set("n", "<leader>d>", delete_buffers_to_right, {
	desc = "Delete all buffers to the right of the current buffer.",
})

-- KEYMAP: <leader>dd
vim.keymap.set("n", "<leader>dd", function()
	kill_buffer("#")
end, { desc = "Remove the current buffer and navigate back to the last active buffer." })

-- KEYMAP: <leader>dn
vim.keymap.set("n", "<leader>dn", function()
	kill_buffer("next")
end, { desc = "Remove the current buffer and navigate to the next buffer." })

-- KEYMAP: <leader>do
vim.keymap.set("n", "<leader>do", "<cmd>%bd|e#<cr>", {
	desc = "Delete all buffers but the current buffer.",
})

-- KEYMAP: <leader>dp
vim.keymap.set("n", "<leader>dp", function()
	kill_buffer("prev")
end, { desc = "Remove the current buffer and navigate to the previous buffer." })

-- KEYMAP: <leader>dt
vim.keymap.set("n", "<leader>dt", "<cmd>tabclose<cr>", {
	desc = "Close the current tab.",
})

-- KEYMAP: <leader>D
vim.keymap.set("n", "<leader>D", delete_file, {
	desc = "Removes a file using 'trash' with a fallback of 'rm'.",
})
