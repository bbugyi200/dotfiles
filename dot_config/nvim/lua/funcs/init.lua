M = {}

function M.remove_buffer(direction)
	vim.cmd("b" .. direction .. " | sp | b# | bd")
end

return M
