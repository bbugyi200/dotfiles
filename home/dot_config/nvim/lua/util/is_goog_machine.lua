--- Module for checking if running on a Google machine
local M = {}

--- Cached result of the Google machine check
M.cached_result = nil

--- Check whether NeoVim is being run from a Google machine.
---@return boolean # True if and only if I am on a Google machine.
function M.is_goog_machine()
	-- Use the module-level variable to cache the result
	if M.cached_result ~= nil then
		return M.cached_result
	end

	local handle = assert(io.popen("uname -a"))
	local result = handle:read("*a")
	handle:close()

	-- Cache the result for future calls
	M.cached_result = result:match("googlers") ~= nil

	return M.cached_result
end

return M.is_goog_machine
