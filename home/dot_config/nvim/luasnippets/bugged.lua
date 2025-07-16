--- Snippets for Buganizer bugs live here.

local bb = require("bb_utils")

local bugged_snippets = {
	-- SNIPPET: a
	s({ trig = "a", desc = "ASSIGNEE=..." }, { t("ASSIGNEE="), i(0) }),
	-- SNIPPET: cl
	s({ trig = "cl", desc = "CHANGELIST+=..." }, { t("CHANGELIST+="), i(0) }),
	-- SNIPPET: p
	s({ trig = "p", desc = "PARENT+=..." }, { t("PARENT+="), i(0) }),
}

return vim.tbl_extend("force", bugged_snippets, bb.snip.get_markdown_snippets())
