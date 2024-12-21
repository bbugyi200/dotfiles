local M = {}

local ls = require("luasnip")
local sn = ls.snippet_node
local i = ls.insert_node

-- Used to replicate UtilSnips ${VISUAL} variable.
function M.get_visual(args, parent, _old_state, default)
	if default == nil then
		ret = ""
	else
		ret = default
	end
	if #parent.snippet.env.LS_SELECT_RAW > 0 then
		return sn(nil, i(1, parent.snippet.env.LS_SELECT_RAW))
	else
		return sn(nil, i(1, ret))
	end
end

return M
