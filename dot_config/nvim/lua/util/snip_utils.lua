--- LuaSnip snippet utilities live here!
local M = {}

local ls = require("luasnip")
local sn = ls.snippet_node
local i = ls.insert_node

--- Used to replicate UtilSnips ${VISUAL} variable.
---
--- TODO(bbugyi): Add @param and @return annotations!
function M.get_visual(_, parent, _, default)
	if #parent.snippet.env.LS_SELECT_RAW > 0 then
		return sn(nil, i(1, parent.snippet.env.LS_SELECT_RAW))
	else
		return sn(nil, i(1, default or ""))
	end
end

return M
