-- Snippets for CodeCompanion chat buffer.

return {
	-- SNIPPET: @e
	s({
		trig = "@e",
		desc = "Auto-snippet for @insert_edit_into_file",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("@insert_edit_into_file") }),
	-- SNIPPET: @@u
	s({
		trig = "@@u",
		desc = "Use @insert_edit_into_file on...",
		snippetType = "autosnippet",
		hidden = true,
	}, {
		t("Use @insert_edit_into_file on "),
		i(1),
		t(". Output calls to the editor() function provided by the editor tool."),
	}),
	-- SNIPPET: @u
	s({
		trig = "@u",
		desc = "Use @insert_edit_into_file on...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("Use @insert_edit_into_file on ") }),
	-- SNIPPET: @@U
	s({
		trig = "@@U",
		desc = "Use @insert_edit_into_file on #buffer{watch} to...",
		snippetType = "autosnippet",
		hidden = true,
	}, {
		t("Use @insert_edit_into_file on #buffer{watch} to "),
		i(1),
		t(". Output calls to the editor() function provided by the editor tool."),
	}),
	-- SNIPPET: @U
	s({
		trig = "@U",
		desc = "Use @insert_edit_into_file on #buffer{watch} to...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("Use @insert_edit_into_file on #buffer{watch} to ") }),
	-- SNIPPET: #b
	s({
		trig = "#b",
		desc = "Auto-snippet for #buffer{watch}...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("#buffer{watch}") }),
}
