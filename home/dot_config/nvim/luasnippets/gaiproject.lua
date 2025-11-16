-- Snippets for ~/.gai/projects/*.gp files live here.

return {
	-- SNIPPET: cs
	s({ trig = "cs", desc = "ChangeSpec template (without TEST TARGETS field)" }, {
		t("NAME: "),
		i(1),
		t({ "", "DESCRIPTION:", "  " }),
		i(2, "Title"),
		t({ "", "", "  " }),
		i(3, "Body"),
		t({ "", "PARENT: None", "CL: None", "STATUS: Unstarted" }),
		i(0),
	}),
	-- SNIPPET: ks
	s({ trig = "ks", desc = "KICKSTART" }, { t({ "KICKSTART:", "" }), t("  "), i(1) }),
	-- SNIPPET: tt
	s({ trig = "tt", desc = "TEST TARGETS field" }, { t("TEST TARGETS: "), i(0) }),
}
