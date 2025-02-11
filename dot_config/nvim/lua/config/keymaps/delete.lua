--- Keymaps that delete the current buffer / file live here.

local kill_buffer = require("util.kill_buffer").kill_buffer

--- Function to remove the current file using 'trash' with a fallback of 'rm'.
---
---@return boolean # Whether the file was removed successfully.
local function delete_file()
	-- Get the current file's full path
	local filename = vim.fn.expand("%:p")

	-- Remove the current buffer and navigate back to the last active buffer.
	kill_buffer("#")

	-- Create a temporary file for stderr.
	local stderr_file = os.tmpname()

	-- Try to trash the file first.
	local command_name = "trash"
	local trash_success = os.execute(command_name .. " " .. vim.fn.shellescape(filename) .. " 2> " .. stderr_file)

	--- Notify the user that the trash/rm command failed (include error message).
	---
	---@param cmd_name string The name of the command that failed.
	local function notify_cmd_failed(cmd_name)
		local err_msg = io.open(stderr_file, "r"):read("*a")
		vim.notify(err_msg, vim.log.levels.WARN, { title = "'" .. cmd_name .. "' error message" })
	end

	-- If trash command fails, try using rm as fallback.
	if trash_success ~= 0 then
		notify_cmd_failed(command_name)

		command_name = "rm"
		local rm_success = os.execute(command_name .. " " .. vim.fn.shellescape(filename) .. " 2> " .. stderr_file)

		-- If both commands fail, show error message.
		if rm_success ~= 0 then
			notify_cmd_failed(command_name)
			vim.notify("Failed to delete file: " .. filename, vim.log.levels.ERROR)
			return false
		end
	end

	vim.notify("Deleted file using '" .. command_name .. "': " .. filename, vim.log.levels.INFO)
	return true
end

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
