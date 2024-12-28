return {
	-- #!b
	s({ trig = "#!b", desc = "Bash SheBang" }, t("#!/bin/bash")),
	-- dt
	s(
		{
			trig = "dt(-?[0-9]+)",
			name = "dt",
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
	-- hm
	s(
		{
			trig = "hm(-?[0-9]+)",
			name = "hm",
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
	-- todu
	s({ trig = "todu", desc = "A TODO that you are responsible for.", hidden = true }, t("TODO(bbugyi): ")),
}
