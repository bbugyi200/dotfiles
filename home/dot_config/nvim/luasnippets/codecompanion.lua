-- Snippets for CodeCompanion chat buffer.
local bb = require("bb_utils")

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
		desc = "Use @editor on...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("Use @editor on ") }),
	-- SNIPPET: @@u
	s({
		trig = "@@u",
		desc = "Use @editor on...",
		snippetType = "autosnippet",
		hidden = true,
	}, {
		t("Use @editor on "),
		i(1),
		t(". Output calls to the editor() function provided by the editor tool."),
	}),
	-- SNIPPET: @U
	s({
		trig = "@U",
		desc = "Use @editor on #buffer{watch} to...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("Use @editor on #buffer{watch} to ") }),
	-- SNIPPET: @@U
	s({
		trig = "@@U",
		desc = "Use @editor on #buffer{watch} to...",
		snippetType = "autosnippet",
		hidden = true,
	}, {
		t("Use @editor on #buffer{watch} to "),
		i(1),
		t(". Output calls to the editor() function provided by the editor tool."),
	}),
	-- SNIPPET: #b
	s({
		trig = "#b",
		desc = "Auto-snippet for #buffer{watch}...",
		snippetType = "autosnippet",
		hidden = true,
	}, { t("#buffer{watch}") }),
}
