--- LuaSnip snippet utilities live here!
--
-- P1: Support comment prefix chars from snippets.
--   [ ] Add get_comment_chars() to snip_utils!
--   [ ] Use to generalize 'todu' snippet!
--   [ ] Add 'todc' to all.lua!
--   [ ] Add 'p0-4' snippets to all.lua!
-- P4: Improve @return annotation of get_visual!

local M = {}

local ls = require("luasnip")
local sn = ls.snippet_node
local i = ls.insert_node
local t = ls.text_node

--- Factory function that is used to replicate UtilSnips ${VISUAL} variable.
---
---@param prefix? string If provided, this string will be prepended to the each selected line.
---@param default_node? any The default node to return if no text is selected.
---@return function # The function that gets used by the dynamic node.
function M.get_visual(prefix, default_node)
	--- The function that gets used by the dynamic node.
	---
	--- P4: Add @param and @return annotations!
	local function inner_get_visual(_, parent)
		---@type table<integer, string>
		local selected_text = parent.snippet.env.LS_SELECT_DEDENT
		local text_table = {}
		if #selected_text > 0 then
			for idx, value in ipairs(selected_text) do
				local val
				if idx > 1 and prefix ~= nil then
					val = prefix .. value
				else
					val = value
				end
				table.insert(text_table, val)
			end
			return sn(nil, { t(text_table), i(1) })
		elseif default_node ~= nil then
			return default_node
		else
			return sn(nil, i(1))
		end
	end

	return inner_get_visual
end

return M
