local at_work = require("util.at_work")

--- Performs an in-place merge of two array-like Lua tables.
---
---@generic T : table
---@param t1 T The first table to merge, which will be modified in-place.
---@param t2 T The second table to merge.
---@return T # The 1st table (t1) with the contents of the 2nd table (t2) merged in.
local function mergeArrays(t1, t2)
	table.move(t2, 1, #t2, #t1 + 1, t1)
	return t1
end

if at_work() then
	local glugs = require("plugins.google.glugs")
	local non_glugs = require("plugins.google.non_glugs")
	return mergeArrays(glugs, non_glugs)
else
	return {}
end
