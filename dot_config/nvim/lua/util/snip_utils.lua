--- LuaSnip snippet utilities live here!
--
-- P1: Support comment prefix chars from snippets.
--   [ ] Add get_comment_chars() to snip_utils!
--   [ ] Use to generalize 'todu' snippet!
--   [ ] Add 'todc' to all.lua!
--   [ ] Add 'p0-4' snippets to all.lua!

local M = {}

local ls = require("luasnip")
local sn = ls.snippet_node
local i = ls.insert_node

--- Used to replicate UtilSnips ${VISUAL} variable.
---
--- P4: Add @param and @return annotations!
function M.get_visual(_, parent, _, default_snippet_node)
	if #parent.snippet.env.LS_SELECT_RAW > 0 then
		return sn(nil, i(1, parent.snippet.env.LS_SELECT_RAW))
	elseif default_snippet_node ~= nil then
		return default_snippet_node
	else
		return sn(nil, i(1))
	end
end

return M
