return {
	-- SNIPPET: #!b
	s({ trig = "#!b", desc = "Bash SheBang" }, t("#!/bin/bash")),
	-- SNIPPET: dt
	s(
		{ trig = "dt", desc = "The current date in YYYY-MM-DD format." },
		{ f(function()
			return os.date("%Y-%m-%d")
		end) }
	),
	-- SNIPPET: dtN
	s(
		{
			trig = "dt(-?[0-9]+)",
			name = "dtN",
			regTrig = true,
			desc = "The date from N days ago / from now in YYYY-MM-DD format",
			hidden = true,
		},
		f(function(_, snip)
			local now = os.time()
			local target_date = now + (tonumber(snip.captures[1]) * 24 * 3600)
			return os.date("%Y-%m-%d", target_date)
		end)
	),
	-- SNIPPET: hm
	s({ trig = "hm", desc = "The current time in HHMM format." }, {
		f(function()
			return os.date("%H%M")
		end),
	}),
	-- SNIPPET: hmN
	s(
		{
			trig = "hm(-?[0-9]+)",
			name = "hmN",
			trigEngine = "pattern",
			desc = "The time from N minutes ago / from now in HHMM format.",
			hidden = true,
		},
		f(function(_, snip)
			local now = os.time()
			local target_time = now + (tonumber(snip.captures[1]) * 60)
			return os.date("%H%M", target_time)
		end)
	),
	-- SNIPPET: todu
	s({ trig = "todu", desc = "A TODO that you are responsible for.", hidden = true }, t("TODO(bbugyi): ")),
}
