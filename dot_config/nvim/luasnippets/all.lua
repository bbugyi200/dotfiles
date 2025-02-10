--- Generates a random date between M and N days from now.
---
--- @param M integer The minimum number of days from now.
--- @param N integer The maximum number of days from now.
--- @return string|osdate
local function get_random_future_date(M, N)
	local currentTime = os.time()
	local randomDays = math.random(M, N)
	local futureTime = currentTime + (randomDays * 86400) -- 86400 seconds in a day
	return os.date("%Y-%m-%d", futureTime)
end

return {
	-- SNIPPET: #!b
	s({ trig = "#!b", desc = "Bash SheBang" }, t("#!/bin/bash")),
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
	-- SNIPPET: todu
	s({ trig = "todu", desc = "A TODO that you are responsible for.", hidden = true }, t("TODO(bbugyi): ")),
}
