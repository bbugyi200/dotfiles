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
local t = ls.text_node

--- Used to replicate UtilSnips' ${VISUAL} variable.
---
--- Factory function that constructs a "dynamic node function" which is
--- intended to be used as an argument to construct a dynamic node[[1]]. See
--- [[2]] for a better idea of what a "dynamic node function" looks like.
---
--- [[1]]: Example: `d(1, get_visual())`
--- [[2]]: https://github.com/L3MON4D3/LuaSnip/blob/master/DOC.md#dynamicnode
---
---@param indent_spaces? string One or more spaces which will be prepended to each selected line except the first.
---@param default_snippet_node? any The dynamic node function will return this snippet node if no text is selected.
---@return function # A "dynamic node function" (as described above).
function M.get_visual(indent_spaces, default_snippet_node)
	local function inner_get_visual(_, parent)
		---@type table<integer, string>
		local selected_text = parent.snippet.env.LS_SELECT_DEDENT
		if #selected_text > 0 then
			---@type table<integer, string>
			local text_table = {}
			for idx, value in ipairs(selected_text) do
				local val
				if idx > 1 and indent_spaces ~= nil then
					val = indent_spaces .. value
				else
					val = value
				end
				table.insert(text_table, val)
			end
			return sn(nil, { t(text_table), i(1) })
		else
			return default_snippet_node or sn(nil, i(1))
		end
	end

	return inner_get_visual
end

return M
