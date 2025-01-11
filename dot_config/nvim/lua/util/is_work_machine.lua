local M = {}

--- Check whether NeoVim is being run from a work (Google) machine.
---
---@return boolean # True if and only if I am on a work machine.
function M.is_work_machine()
	local handle = assert(io.popen("command -v /google/bin/releases/cider/ciderlsp/ciderlsp"))
	local result = handle:read("*a")
	handle:close()
	return result ~= ""
end

return M
