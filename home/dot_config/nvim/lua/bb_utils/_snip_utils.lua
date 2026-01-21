--- LuaSnip snippet utilities live here!
--
-- P1: Support comment prefix chars from snippets.
--   [ ] Add get_comment_chars() to snip_utils!
--   [ ] Use to generalize 'todu' snippet!
--   [ ] Add 'todc' to all.lua!
--   [ ] Add 'p0-4' snippets to all.lua!

local M = {}

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
	local ls = require("luasnip")
	local sn = ls.snippet_node
	local i = ls.insert_node
	local t = ls.text_node

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

--- Returns a table of common snippets that can be used across multiple filetypes.
---@return table # A table of LuaSnip snippets
function M.get_markdown_snippets()
	local ls = require("luasnip")
	local d = ls.dynamic_node
	local s = ls.snippet
	local i = ls.insert_node
	local t = ls.text_node
	local fmt = require("luasnip.extras.fmt").fmt
	local editor_tool_name = "{insert_edit_into_file}"

	return {
		-- SNIPPET: ?
		s({ trig = "?", desc = "Can you ...?" }, { t("Can you "), i(1), t("?") }),
		-- SNIPPET: @e
		s({
			trig = "@e",
			desc = "Auto-snippet for @" .. editor_tool_name,
			snippetType = "autosnippet",
			hidden = true,
		}, { t("@" .. editor_tool_name) }),
		-- SNIPPET: @@u
		s({
			trig = "@@u",
			desc = "Use @" .. editor_tool_name .. " to...",
			snippetType = "autosnippet",
			hidden = true,
		}, {
			t("Use @" .. editor_tool_name .. " to "),
			i(1),
			t(
				". Output calls to the "
					.. editor_tool_name
					.. "() function provided by the "
					.. editor_tool_name
					.. " tool."
			),
		}),
		-- SNIPPET: @u
		s({
			trig = "@u",
			desc = "Use @" .. editor_tool_name .. " on...",
			snippetType = "autosnippet",
			hidden = true,
		}, { t("Use @" .. editor_tool_name .. " on ") }),
		-- SNIPPET: @@U
		s({
			trig = "@@U",
			desc = "Use @" .. editor_tool_name .. " on #{buffer}{watch} to...",
			snippetType = "autosnippet",
			hidden = true,
		}, {
			t("Use @" .. editor_tool_name .. " on #{buffer}{watch} to "),
			i(1),
			t(
				". Output calls to the "
					.. editor_tool_name
					.. "() function provided by the "
					.. editor_tool_name
					.. " tool."
			),
		}),
		-- SNIPPET: @U
		s({
			trig = "@U",
			desc = "Use @" .. editor_tool_name .. " on #{buffer}{watch} to...",
			snippetType = "autosnippet",
			hidden = true,
		}, { t("Use @" .. editor_tool_name .. " on #{buffer}{watch} to ") }),
		-- SNIPPET: bld
		s({ trig = "bld", desc = "Build failure" }, {
			t("Can you help me fix this build (see the build"),
			i(1),
			t(
				".txt file)? When you're done, run the appropriate `rabbit build` command, then fix the new"
					.. " failures (if any), and repeat until the command is successful."
			),
		}),
		-- SNIPPET: cb
		s(
			{ trig = "cb", desc = "A code block." },
			fmt(
				[[
      ```{}
      {}
      ```
    ]],
				{ i(1), d(2, M.get_visual()) }
			)
		),
		-- SNIPPET: cps
		s(
			{ trig = "cps", desc = "Context / Problem / Solution" },
			fmt(
				[[
        **CONTEXT**
        * {context}

        **PROBLEM**
        * {problem}

        **SOLUTION**
        * {solution}
        ]],
				{
					context = i(1),
					problem = i(2),
					solution = i(3),
				}
			)
		),
		-- SNIPPET: cr
		s(
			{ trig = "cr", desc = "Critique change request help." },
			{ t("Can you help me address the Critique comments?") }
		),
		-- SNIPPET: di
		s({ trig = "di", desc = "diff_*.txt file explanation" }, {
			t("The diff"),
			i(1),
			t("."),
			i(2, "txt"),
			t(" file contains a diff of the changes made by "),
			i(3, "the current CL"),
			t("."),
			i(4),
		}),
		-- SNIPPET: er
		s(
			{ trig = "er", desc = "err_*.txt file explanation" },
			{ t("The err"), i(1), t(".txt file contains "), i(2, "the failure output"), t(".") }
		),
		-- SNIPPET: fi
		s({ trig = "fi", desc = "the ____ file" }, { t("the "), i(1), t(" file") }),
		-- SNIPPET: fii
		s({ trig = "fii", desc = "The ____ file" }, { t("The "), i(1), t(" file") }),
		-- SNIPPET: fix
		s({ trig = "fix", desc = "Can you help me fix this?" }, { t("Can you help me fix this?") }),
		-- SNIPPET: fixt
		s({ trig = "fixt", desc = "Can you help me fix this test?" }, { t("Can you help me fix this test?") }),
		-- SNIPPET: fixx
		s(
			{ trig = "fixx", desc = "Can you help me fix these?" },
			{ t("Can you help me diagnose the root cause of this issue and fix it?") }
		),
		-- SNIPPET: help
		s({ trig = "help", desc = "Can you help me...?" }, { t("Can you help me "), i(1), t("?") }),
		-- SNIPPET: helpp
		s({ trig = "helpp", desc = "Can you now help me...?" }, { t("Great! Can you now help me "), i(1), t("?") }),
		-- SNIPPET: impl
		s({ trig = "impl", desc = "Can you help me implement...?" }, { t("Can you help me implement "), i(1), t("?") }),
		-- SNIPPET: iow
		s({ trig = "iow", desc = "In other words, _____ ..." }, { t("In other words, "), i(1) }),
		-- SNIPPET: loop
		s({ trig = "loop", desc = "Repeatedly run a command until it passed." }, {
			t("When you're done, run the `"),
			i(1),
			t("` command, then fix the new failures (if any), and repeat until the command is successful."),
		}),
		-- SNIPPET: pin
		s(
			{ trig = "pin", desc = "Describe pinned files." },
			{ t("I've pinned some other "), i(1), t(" files to help you figure this out.") }
		),
		-- SNIPPET: try
		s(
			{ trig = "try", desc = "Try again now that you have access to the ______ file." },
			{ t("Try again now that you have access to the "), i(1), t(" file.") }
		),
		-- SNIPPET: tryy
		s(
			{ trig = "tryy", desc = "Try again now that you have access to some more files." },
			{ t("Try again now that you have access to some more files.") }
		),
		-- SNIPPET: tst
		s({ trig = "tst", desc = "Test failure" }, {
			t("Can you help me fix this test (see the test"),
			i(1),
			t(
				".txt file)? When you're done, run the appropriate `rabbit test` command, then fix the new"
					.. " failures (if any), and repeat until the command is successful."
			),
		}),
	}
end

return M
