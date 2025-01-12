--- LuaSnip snippet utilities live here!
--
-- P1: Support comment prefix chars from snippets.
--   [ ] Add get_comment_chars() to snip_utils!
--   [ ] Use to generalize 'todu' snippet!

local M = {}

local ls = require("luasnip")
local sn = ls.snippet_node
local i = ls.insert_node

--- Used to replicate UtilSnips ${VISUAL} variable.
---
--- P4: Add @param and @return annotations!
function M.get_visual(_, parent, _, default)
	if #parent.snippet.env.LS_SELECT_RAW > 0 then
		return sn(nil, i(1, parent.snippet.env.LS_SELECT_RAW))
	else
		return sn(nil, i(1, default or ""))
	end
end

return M
