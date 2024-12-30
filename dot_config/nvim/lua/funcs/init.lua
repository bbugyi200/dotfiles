M = {}

-- Remove a buffer and navigate to another buffer specified via @direction.
--
---@param direction string A string indicating a relative buffer direction (ex: 'next', 'prev', '#').
---@return nil
function M.remove_buffer(direction)
	vim.cmd("b" .. direction .. " | sp | b# | bd")
end

-- Source @file, if it exists.
--
---@param file string A *.vim or *.lua file to be sourced.
---@return nil
function M.source_if_exists(file)
	local expanded = vim.fn.expand(file)
	if vim.fn.filereadable(expanded) == 1 then
		vim.cmd("source " .. expanded)
	end
end

-- Check whether NeoVim is being run from a Google machine.
--
---@return boolean
function M.on_google_machine()
	local handle = assert(io.popen("command -v /google/bin/releases/cider/ciderlsp/ciderlsp"))
	local result = handle:read("*a")
	handle:close()
	return result ~= ""
end

return M
