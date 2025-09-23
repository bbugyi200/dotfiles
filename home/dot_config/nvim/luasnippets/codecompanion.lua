-- Snippets for CodeCompanion chat buffer.
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
	-- SNIPPET: #b
	s({
		trig = "#b",
		desc = "Auto-snippet for #{buffer}{watch}...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("#{buffer}{watch}") }),
	-- SNIPPET: cr
	s(
		{ trig = "cr", desc = "Critique change request help." },
		{ t("Can you help me address the Critique comments left by "), i(1), t("@?") }
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
	-- SNIPPET: fixx
	s({ trig = "fixx", desc = "Can you help me fix these?" }, { t("Can you help me fix these?") }),
	-- SNIPPET: help
	s({ trig = "help", desc = "Can you help me...?" }, { t("Can you help me "), i(1), t("?") }),
	-- SNIPPET: helpp
	s({ trig = "helpp", desc = "Can you now help me...?" }, { t("Can you now help me "), i(1), t("?") }),
	-- SNIPPET: impl
	s({ trig = "impl", desc = "Can you help me implement...?" }, { t("Can you help me implement "), i(1), t("?") }),
	-- SNIPPET: iow
	s({ trig = "iow", desc = "In other words, _____ ..." }, { t("In other words, "), i(1) }),
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
}
