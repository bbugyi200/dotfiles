-- Check whether NeoVim is being run from a Google machine.
--
---@return boolean # True iff I am on a work machine.
local function at_work()
	local handle = assert(io.popen("command -v /google/bin/releases/cider/ciderlsp/ciderlsp"))
	local result = handle:read("*a")
	handle:close()
	return result ~= ""
end

return at_work
