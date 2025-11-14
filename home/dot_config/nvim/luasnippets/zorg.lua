-- Snippets for *.zo files.

local bb = require("bb_utils")

--- Returns the current datetime using the YYMMDD@HHMM format.
local function get_zdatetime()
	return string.sub(tostring(os.date("%Y%m%d@%H%M")), 3)
end

--- Returns the current date using the YYMMDD format.
local function get_zdate()
	return string.sub(tostring(os.date("%Y%m%d")), 3)
end

--- Returns start and end times for a pomodoro session.
--- Start is the next minute divisible by 5 (including current), end is duration minutes later.
--- @param duration number Duration in minutes to add to start time
--- @param time_offset number? Optional offset in minutes to subtract from current time (default: 0)
--- @return string Formatted string "start::HHMM end::HHMM"
local function get_start_end_time(duration, time_offset)
	time_offset = time_offset or 0

	-- Get current time and apply offset
	local now_timestamp = os.time() - (time_offset * 60)
	local now = os.date("*t", now_timestamp)
	local current_hour = now.hour
	local current_min = now.min

	-- Calculate next minute divisible by 5 (including current)
	local start_min = math.ceil(current_min / 5) * 5
	local start_hour = current_hour

	-- Handle minute overflow
	if start_min >= 60 then
		start_min = 0
		start_hour = start_hour + 1
		if start_hour >= 24 then
			start_hour = 0
		end
	end

	-- Calculate end time (duration minutes later)
	local end_min = start_min + duration
	local end_hour = start_hour

	-- Handle minute overflow for end time
	while end_min >= 60 do
		end_min = end_min - 60
		end_hour = end_hour + 1
		if end_hour >= 24 then
			end_hour = 0
		end
	end

	-- Format as HHMM
	local start_str = string.format("%02d%02d", start_hour, start_min)
	local end_str = string.format("%02d%02d", end_hour, end_min)

	return string.format("start::%s end::%s", start_str, end_str)
end

return {
	-- SNIPPET: #
	s({ trig = "#", desc = "An H1 zorg header.", hidden = true }, { t("################################ ") }),
	-- SNIPPET: #2
	s({
		trig = "^#2",
		name = "#2",
		regTrig = true,
		desc = "An H2 zorg header.",
		hidden = true,
		snippetType = "autosnippet",
	}, { t("======================== ") }),
	-- SNIPPET: #3
	s({
		trig = "^#3",
		name = "#3",
		regTrig = true,
		desc = "An H3 zorg header.",
		hidden = true,
		snippetType = "autosnippet",
	}, { t("++++++++++++++++ ") }),
	-- SNIPPET: #4
	s({
		trig = "^#4",
		name = "#4",
		regTrig = true,
		desc = "An H4 zorg header.",
		hidden = true,
		snippetType = "autosnippet",
	}, { t("-------- ") }),
	-- SNIPPET: blo
	s({ trig = "blo", desc = "Shortcut for [[lib/blogs/*]] links." }, { t("[[lib/blogs"), i(1), t("]]") }),
	-- SNIPPET: bk
	s({ trig = "bk", desc = "Shortcut for [[lib/books/*]] links." }, { t("[[lib/books"), i(1), t("]]") }),
	-- SNIPPET: c
	s({ trig = "c", desc = "Easy creation of CodeSearch links." }, { t("http://cs/") }),
	-- SNIPPET: cb
	s(
		{ trig = "cb", desc = "A code block." },
		fmt(
			[[
      ```{}
      {}
      ```
    ]],
			{ i(1), d(2, bb.snip.get_visual()) }
		)
	),
	-- SNIPPET: chap
	s(
		{ trig = "chap", desc = "A chapter reference note template." },
		fmt(
			[===[
- [[read]] LID::chapter_{N} | pg::{pg}
	* status:: UNREAD
	* title:: {title}
    ]===],
			{ N = i(1), pg = i(2), title = i(3) }
		)
	),
	-- SNIPPET: cl
	s(
		{ trig = "cl", desc = "Snippet for @CL todos." },
		fmt(
			[===[
      - ID::cl_{id}
        * {title}
      > P0 Submit [#cl_{id}]
      o P0 +{project} Mail [#cl_{id}] @CL
    ]===],
			{ id = i(1), title = i(2), project = i(3) },
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: cr
	s(
		{ trig = "cr", desc = "Reply to CRs from %johndoe on [!cl_foobar]!" },
		{ t("Reply to CRs from "), i(1), t(" on "), i(2), t("!") }
	),
	-- SNIPPET: doc
	s({ trig = "doc", desc = "Shortcut for [[lib/manual/*]] links." }, { t("[[lib/docs"), i(1), t("]]") }),
	-- SNIPPET: dz
	s({ trig = "dz", desc = "Shortcut for YYMMDD date." }, { f(get_zdatetime), t(" ") }),
	-- SNIPPET: e
	s({ trig = "e", desc = "end:: [[pomodoro]] header property." }, { t("end::") }),
	-- SNIPPET: fno
	s(
		{ trig = "fno", desc = "A FLEETING NOTES zorg bullet." },
		{ t({ "FLEETING NOTES:", "  - [ ] [[lit_review" }), i(1), t("]]") }
	),
	-- SNIPPET: ftap
	s({ trig = "ftap", desc = "Fix TAP tests for a CL." }, { t("Fix any failing test in "), i(1), t("!") }),
	-- SNIPPET: g
	s({ trig = "g", desc = "Easy creation of go-links." }, { t("http://go/") }),
	-- SNIPPET: ib
	s({ trig = "ib", desc = "An INSPIRED BY zorg bullet." }, { t("INSPIRED BY: ") }),
	-- SNIPPET: id
	s({ trig = "id", desc = "ID:: global ID property." }, { t("ID::") }),
	-- SNIPPET: im
	s({ trig = "im", desc = "Shortcut for [[img/*]] links." }, { t("[[img"), i(1), t("]]") }),
	-- SNIPPET: li
	s({ trig = "li", desc = "A LINKS zorg bullet." }, { t("LINKS: ") }),
	-- SNIPPET: lib
	s({ trig = "lib", desc = "Shortcut for [[lib/*]] links." }, { t("[[lib"), i(1), t("]]") }),
	-- SNIPPET: lid
	s({ trig = "lid", desc = "LID:: local ID property." }, { t("LID::") }),
	-- SNIPPET: lno
	s({ trig = "lno", desc = "A LITERATURE NOTES zorg bullet." }, { t({ "LITERATURE NOTES:", "  - " }), i(1) }),
	-- SNIPPET: no
	s({ trig = "no", desc = "A NOTES zorg bullet." }, {
		t({ "NOTES:", "" }),
		f(function()
			return "  - " .. get_zdatetime() .. " "
		end),
	}),
	-- SNIPPET: oN
	s({
		trig = "^o([0-9])",
		name = "oN",
		regTrig = true,
		desc = "A prioritized zorg todo.",
		hidden = true,
		snippetType = "autosnippet",
	}, { t("o "), f(function(_, snip)
		return "P" .. snip.captures[1] .. " "
	end) }),
	-- SNIPPET: ow
	s({ trig = "ow", desc = "o P4 @WAIT..." }, { t("o P4 @WAIT ") }),
	-- SNIPPET: owl
	s({ trig = "owl", desc = "o P4 @WAIT for LGTM from..." }, { t("o P4 @WAIT for LGTM from ") }),
	-- SNIPPET: p
	s({
		trig = "p([0-9]+)",
		name = "p",
		regTrig = true,
		desc = "An H2 [[pomodoro]] header.",
		hidden = true,
	}, { t("======================== p::"), f(function(_, snip)
		return snip.captures[1]
	end) }),
	-- SNIPPET: pap
	s({ trig = "pap", desc = "Shortcut for [[lib/papers/*]] links." }, { t("[[lib/papers"), i(1), t("]]") }),
	-- SNIPPET: ref
	s(
		{ trig = "ref", desc = "A reference note template." },
		fmt(
			[===[
      - {tag} [[read]] ID::{id}
        | LINKS: {links}
        * file:: {file}
        * status:: UNREAD
        * url:: {url}
    ]===],
			{ tag = i(1), id = i(2), links = i(3), file = i(4), url = i(5) }
		)
	),
	-- SNIPPET: s
	s({ trig = "s", desc = "start:: [[pomodoro]] header property." }, { t("start::") }),
	-- SNIPPET: se[0-9]+ or se[0-9]+-[0-9]+
	s({
		trig = "se([0-9]*)%-?([0-9]*)",
		name = "se",
		regTrig = true,
		desc = "start/end times (seN for N*5 mins, seN-M for N*5 mins at NOW-5*M). Defaults: N=5, M=1 (if dash present).",
		hidden = true,
	}, {
		f(function(_, snip)
			local duration_multiplier = tonumber(snip.captures[1]) or 5
			local time_offset_multiplier = tonumber(snip.captures[2])

			-- If there's a dash in the trigger and M is not provided, default M to 1
			if string.find(snip.trigger, "-") and time_offset_multiplier == nil then
				time_offset_multiplier = 1
			else
				time_offset_multiplier = time_offset_multiplier or 0
			end

			-- Multiply by 5
			local duration = duration_multiplier * 5
			local time_offset = time_offset_multiplier * 5

			return get_start_end_time(duration, time_offset)
		end),
	}),
	-- SNIPPET: td
	s({ trig = "td", desc = "@TODO context tag" }, { t("@TODO") }),
	-- SNIPPET: w
	s({ trig = "w", desc = "@WIP context tag" }, { t("@WIP") }),
	-- SNIPPET: z
	s({ trig = "z", desc = "ZID link" }, {
		t("["),
		f(get_zdate),
		t("#0"),
		i(1),
		t("]"),
	}),
}
