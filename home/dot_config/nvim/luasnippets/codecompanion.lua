-- Snippets for CodeCompanion chat buffer.

return {
	-- SNIPPET: @e
	s({
		trig = "@e",
		desc = "Auto-snippet for @editor",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("@editor") }),
	-- SNIPPET: @u
	s({
		trig = "@u",
		desc = "Use @editor on #buffer{watch} to...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("Use @editor on #buffer{watch} to ") }),
	-- SNIPPET: #b
	s({
		trig = "#b",
		desc = "Auto-snippet for #buffer{watch}...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("#buffer{watch}") }),
}
