--- Snippets for Buganizer bugs live here.

return {
	-- SNIPPET: a
	s({ trig = "a", desc = "ASSIGNEE=..." }, { t("ASSIGNEE="), i(0) }),
	-- SNIPPET: cl
	s({ trig = "cl", desc = "CHANGELIST+=..." }, { t("CHANGELIST+="), i(0) }),
	-- SNIPPET: cpsr
	s(
		{ trig = "cpsr", desc = "Context / Problem / Solution / Resources" },
		fmt(
			[[
      **Context**
      * {context}

      **Problem**
      * {problem}

      **Solution**
      * {solution}

      **Resources**
      * {resources}
      ]],
			{
				context = i(1),
				problem = i(2),
				solution = i(3),
				resources = i(4),
			}
		)
	),
	-- SNIPPET: p
	s({ trig = "p", desc = "PARENT+=..." }, { t("PARENT+="), i(0) }),
}
