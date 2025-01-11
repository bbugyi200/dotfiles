local is_work_machine = require("util.is_work_machine").is_work_machine

--- Performs an in-place merge of two array-like Lua tables.
---
---@generic T : table
---@param t1 T The first table to merge, which will be modified in-place.
---@param t2 T The second table to merge.
---@return T # The 1st table (t1) with the contents of the 2nd table (t2) merged in.
local function merge_tables(t1, t2)
	table.move(t2, 1, #t2, #t1 + 1, t1)
	return t1
end

if is_work_machine() then
	return merge_tables(require("plugins.google.glugs"), require("plugins.google.non_glugs"))
else
	return {}
end
