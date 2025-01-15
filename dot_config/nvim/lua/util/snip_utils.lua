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

--- Used to replicate UtilSnips ${VISUAL} variable.
---
---@param indent_spaces? string One or moe spaces to prepend to each line.
---@param default any The default snippet node to return if no text is selected.
---@return function # The function that gets used by the dynamic node.
function M.get_visual(indent_spaces, default)
	--- The function that gets used by the dynamic node.
	---
	--- P4: Add @param and @return annotations!
	local function inner_get_visual(_, parent)
		---@type table<integer, string>
		local selected_text = parent.snippet.env.LS_SELECT_DEDENT
		local text_table = {}
		if #selected_text > 0 then
			vim.notify(selected_text[1])
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
		elseif default ~= nil then
			return default
		else
			return sn(nil, i(1))
		end
	end

	return inner_get_visual
end

return M
