--- Generates a random date between [min] and [max] days from now.
---
--- @param min integer The minimum number of days from now.
--- @param max integer The maximum number of days from now.
--- @return string|osdate # Random date between [min] and [max] days from now in YYYY-MM-DD format.
local function get_random_future_date(min, max)
	local current_time = os.time()
	local random_days = math.random(min, max)
	local future_time = current_time + (random_days * 24 * 60 * 60)
	return os.date("%Y-%m-%d", future_time)
end

return {
	-- SNIPPET: #!b
	s({ trig = "#!b", desc = "Bash SheBang" }, t("#!/bin/bash")),
	-- SNIPPET: dM:N
	s({
		trig = "d([1-9][0-9]*):([1-9][0-9]*)",
		name = "dM:N",
		regTrig = true,
		desc = "A random date between M and N days from now.",
		hidden = true,
	}, { f(function(_, snip)
		return get_random_future_date(snip.captures[1], snip.captures[2])
	end) }),
	-- SNIPPET: dN
	s(
		{
			trig = "d(-?[0-9]+)",
			name = "dN",
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
	-- SNIPPET: h
	s({ trig = "h", desc = "Easy creation of HTTP links." }, { t("http://") }),
	-- SNIPPET: tN
	s(
		{
			trig = "t(-?[0-9]+)",
			name = "tN",
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
	-- SNIPPET: tod
	s({ trig = "tod", desc = "TODO(bbugyi): some todo comment..." }, { t("TODO(bbugyi): ") }),
}
