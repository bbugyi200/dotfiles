--- Check whether NeoVim is being run from a Google machine.
---
---@return boolean # True if and only if I am on a Google machine.
local function is_goog_machine()
	local handle = assert(io.popen("uname -a"))
	local result = handle:read("*a")
	handle:close()
	return result:match("googlers") ~= nil
end

return is_goog_machine
