local M = {}

---@alias BufferDirection
---| "#" The last active buffer.
---| "next" The next buffer.
---| "prev" The previous buffer.
---
--- Remove a buffer and navigate to another buffer specified via {direction}.
---
---@param direction BufferDirection A string indicating a relative buffer direction.
function M.kill_buffer(direction)
	vim.cmd("b" .. direction .. " | sp | b# | bd")
end

return M
