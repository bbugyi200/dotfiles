-- Snippets for CodeCompanion chat buffer.
local editor_tool_name = "{insert_edit_into_file}"
return {
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
	-- SNIPPET: #b
	s({
		trig = "#b",
		desc = "Auto-snippet for #{buffer}{watch}...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("#{buffer}{watch}") }),
	-- SNIPPET: cl
	s(
		{ trig = "cl", desc = "diff_*.txt file explanation" },
		{ t("The "), i(1), t(".txt file contains a diff of the changes made by the current CL.") }
	),
	-- SNIPPET: impl
	s({ trig = "impl", desc = "Can you help me implement..." }, { t("Can you help me implement "), i(1), t("?") }),
}
