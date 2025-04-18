--- Snippets for Buganizer bugs live here.

return {
	-- SNIPPET: a
	s({ trig = "a", desc = "ASSIGNEE=..." }, { t("ASSIGNEE="), i(0) }),

	-- SNIPPET: cl
	s({ trig = "cl", desc = "CHANGELIST+=..." }, { t("CHANGELIST+="), i(0) }),

	-- SNIPPET: cps
	s(
		{ trig = "cps", desc = "Context / Problem / Solution" },
		fmt(
			[[
      **Context**
      * {}

      **Problem**
      * {}

      **Solution**
      * {}
      ]],
			{
				i(1),
				i(2),
				i(0),
			}
		)
	),

	-- SNIPPET: p
	s({ trig = "p", desc = "PARENT+=..." }, { t("PARENT+="), i(0) }),
}
