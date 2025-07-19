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
	-- SNIPPET: fix
	s({ trig = "fix", desc = "Can you help me fix this?" }, { t("Can you help me fix this?") }),
	-- SNIPPET: fixx
	s({ trig = "fixx", desc = "Can you help me fix these?" }, { t("Can you help me fix these?") }),
	-- SNIPPET: help
	s({ trig = "help", desc = "Can you help me...?" }, { t("Can you help me "), i(1), t("?") }),
	-- SNIPPET: impl
	s({ trig = "impl", desc = "Can you help me implement...?" }, { t("Can you help me implement "), i(1), t("?") }),
	-- SNIPPET: plan
	s({ trig = "plan", desc = "Prefix to prompt to plan before proposing code changes." }, {
		t(
			"Create a plan for helping me with the following prompt. Let me know what "
				.. "additional information would be useful / which files you would benefit "
				.. "from me sharing that I have not already shared with you: "
		),
	}),
}
