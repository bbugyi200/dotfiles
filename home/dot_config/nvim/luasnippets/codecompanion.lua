-- Snippets for CodeCompanion chat buffer.

return {
	-- SNIPPET: @e
	s({ trig = "@e", desc = "Auto-snippet for @editor", snippetType = "autosnippet" }, { t("@editor ") }),
	-- SNIPPET: #b
	s({ trig = "#b", desc = "Auto-snippet for #buffer", snippetType = "autosnippet" }, { t("#buffer ") }),
}
