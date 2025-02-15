--- Keymaps that delete the current buffer / file live here.

local kill_buffer = require("util.kill_buffer").kill_buffer
local delete_file = require("util.delete_file")

-- KEYMAP(N): <leader>dd
vim.keymap.set("n", "<leader>dd", function()
	kill_buffer("#")
end, { desc = "Remove the current buffer and navigate back to the last active buffer." })

-- KEYMAP(N): <leader>dn
vim.keymap.set("n", "<leader>dn", function()
	kill_buffer("next")
end, { desc = "Remove the current buffer and navigate to the next buffer." })

-- KEYMAP(N): <leader>dp
vim.keymap.set("n", "<leader>dp", function()
	kill_buffer("prev")
end, { desc = "Remove the current buffer and navigate to the previous buffer." })

-- KEYMAP(N): <leader>D
vim.keymap.set("n", "<leader>D", delete_file, {
	desc = "Removes a file using 'trash' with a fallback of 'rm'.",
})
