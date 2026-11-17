-- Pure ping-window model and presentation for the Hammerspoon ping menu bar.
-- This module is hs-free (only os.date for clock text) so the ping-menubar
-- phase can consume it from the runtime and busted can drive it directly.
local M = {}

-- Shared ping-stream constants. The window size is the runtime `window_size`
-- config field (see CONFIG_RELATIVE_PATH). Common stream values mirror
-- `home/bin/executable_tmux_ping`; web-probe and event-log settings are Lua-only.
M.TARGET = "8.8.8.8"
M.INTERVAL_SECONDS = 2
M.DEFAULT_WINDOW_SIZE = 30
M.MIN_WINDOW_SIZE = 3
M.MAX_WINDOW_SIZE = 99
M.CONFIG_RELATIVE_PATH = ".config/ping_window/config"
M.HANDOFF_SECONDS = 6
M.STALE_SECONDS = 6
M.OFFLINE_AFTER_FAILURES = 3
-- A healthy window has at least 90% replies: successes * 10 >= total * 9.
M.PING_PATH = "/sbin/ping"
M.SLOW_MS = 500
M.RTT_KEEP = 5
M.SLOW_MIN_REPLIES = 3
M.PING_WAIT_MS = 500
M.PING_ARGS = { "-n", "-q", "-c", "1", "-W", tostring(M.PING_WAIT_MS), M.TARGET }
M.WEB_FRESH_SECONDS = 15
M.WEB_CHECK_GRACE_SECONDS = 10
M.WEB_URL = "http://captive.apple.com/hotspot-detect.html"
M.CURL_PATH = "/usr/bin/curl"
M.WEB_TIMEOUT_SECONDS = 8
M.WEB_CONNECT_TIMEOUT_SECONDS = 6
M.WEB_RECHECK_SECONDS = 10
M.WEB_SHOW_SECONDS = 300
M.EVENTS_BASENAME = "ping_window_events.tsv"
M.EVENTS_MAX_LINES = 2000
M.EVENTS_KEEP_LINES = 1000
M.CURL_ARGS = {
	"-sS",
	"--max-time",
	tostring(M.WEB_TIMEOUT_SECONDS),
	"--connect-timeout",
	tostring(M.WEB_CONNECT_TIMEOUT_SECONDS),
	"--max-redirs",
	"0",
	"--noproxy",
	"*",
	"-w",
	"\n__PING_WINDOW__ %{http_code} %{time_namelookup} %{time_connect}",
	M.WEB_URL,
}
M.STATE_BASENAME = "tmux_ping_state"

M.OK_COLOR = "#30d158"
M.WARN_COLOR = "#FF9F0A"
M.ALERT_COLOR = "#E3413B"
M.BADGE_TEXT_COLOR = "#FFFFFF"

M.GLYPH_OK = "✓" -- U+2713, usable connectivity
M.GLYPH_FAIL = "✗" -- U+2717, negative connectivity evidence
M.GLYPH_STALE = "◌" -- U+25CC, no recent pings
M.DASH = "–" -- U+2013, empty-window count

local NBSP = "\194\160" -- U+00A0, menu bar edge pad
local FIGURE_SPACE = "\226\128\135" -- U+2007, fixed-width count pad
local HISTORY_REPLY = "●" -- U+25CF, answered sample cell
local HISTORY_SLOW = "◐" -- U+25D0, slow reply cell
local HISTORY_MISS = "○" -- U+25CB, missed sample cell
local HISTORY_EMPTY = "·" -- U+00B7, unfilled sample cell
local MIDDLE_DOT = "·" -- U+00B7, summary/info separator
local ELLIPSIS = "…" -- U+2026, action row suffix

local function codepoint_length(text)
	local count = 0
	local value = tostring(text or "")
	for index = 1, #value do
		local byte = value:byte(index)
		if byte < 128 or byte >= 192 then
			count = count + 1
		end
	end
	return count
end

local function is_digits(text)
	return type(text) == "string" and text:match("^%d+$") ~= nil
end

local function trim_blanks(text)
	return (tostring(text):match("^[ \t]*(.-)[ \t]*$"))
end

-- Parse the shared window-size config text per the contract both producers
-- share: line by line (including a last line without a newline), one trailing
-- CR stripped, blank and `#` lines skipped, split at the first `=`, only the
-- last `window_size` line winning, valid only for 3-99 with no leading zero.
-- Returns window_size, problem (problem non-nil only for present-but-invalid).
function M.parse_config(text)
	if type(text) ~= "string" or text == "" then
		return M.DEFAULT_WINDOW_SIZE, nil
	end
	local last = nil
	local has_key = false
	-- Iterate lines including a final line without a newline.
	local position = 1
	while position <= #text + 1 do
		local newline_at = text:find("\n", position, true)
		local line
		if newline_at == nil then
			line = text:sub(position)
			position = #text + 2
		else
			line = text:sub(position, newline_at - 1)
			position = newline_at + 1
		end
		if newline_at == nil and line == "" then
			break
		end
		if line:sub(-1) == "\r" then
			line = line:sub(1, -2)
		end
		line = trim_blanks(line)
		if line ~= "" and line:sub(1, 1) ~= "#" then
			local equals_at = line:find("=", 1, true)
			if equals_at ~= nil then
				local key = trim_blanks(line:sub(1, equals_at - 1))
				local value = trim_blanks(line:sub(equals_at + 1))
				if key == "window_size" then
					last = value
					has_key = true
				end
			end
		end
		if newline_at == nil then
			break
		end
	end
	if not has_key then
		return M.DEFAULT_WINDOW_SIZE, nil
	end
	local size = tonumber(last)
	if
		type(last) == "string"
		and last:match("^[1-9][0-9]?$") ~= nil
		and size ~= nil
		and size >= M.MIN_WINDOW_SIZE
		and size <= M.MAX_WINDOW_SIZE
	then
		return size, nil
	end
	return M.DEFAULT_WINDOW_SIZE, string.format("invalid window_size '%s'; using %d", last, M.DEFAULT_WINDOW_SIZE)
end

-- Newest n characters of a results string (oldest first).
function M.newest(results, n)
	local value = tostring(results or "")
	if type(n) ~= "number" or n < 0 then
		return value
	end
	if #value <= n then
		return value
	end
	return value:sub(-n)
end

local function parse_rtts(value)
	local rtts = {}
	for part in (value .. ","):gmatch("(.-),") do
		if not is_digits(part) or #part > 6 then
			return nil
		end
		table.insert(rtts, tonumber(part))
	end
	if #rtts == 0 or #rtts > M.RTT_KEEP then
		return nil
	end
	return rtts
end

local function parse_web(value)
	local verdict, at, ms = value:match("^([a-z]+),(%d+),([^,]+)$")
	if verdict ~= "ok" and verdict ~= "fail" and verdict ~= "portal" then
		return nil
	end
	if ms ~= "-" and not is_digits(ms) then
		return nil
	end
	return { verdict = verdict, at = tonumber(at), ms = tonumber(ms) }
end

-- State v2 accepts v1 unchanged. Bad known values are absent, unknown keys
-- are ignored, and the last occurrence wins (including a malformed one).
function M.parse_state(text)
	if type(text) ~= "string" or text == "" then
		return nil
	end
	if text:sub(-1) == "\n" then
		text = text:sub(1, -2)
	end
	local heartbeat, producer, sampled, results, extra = text:match("^(%S+) (%S+) (%S+) (%S+)(.*)$")
	if heartbeat == nil or (producer ~= "hammerspoon" and producer ~= "tmux") then
		return nil
	end
	if not is_digits(heartbeat) or not is_digits(sampled) then
		return nil
	end
	if results == "-" then
		results = ""
	elseif #results > M.MAX_WINDOW_SIZE or results:match("^[01s]+$") == nil then
		return nil
	end
	local state =
		{ heartbeat = tonumber(heartbeat), producer = producer, sampled = tonumber(sampled), results = results }
	while extra ~= "" do
		local key, value, rest = extra:match("^ ([a-z][a-z0-9_]*)=([^%s]*)(.*)$")
		if not key then
			return nil
		end
		if key == "rtt" then
			state.rtt = parse_rtts(value)
		elseif key == "web" then
			state.web = parse_web(value)
		elseif key == "check" then
			state.check = is_digits(value) and tonumber(value) or nil
		end
		extra = rest
	end
	return state
end

function M.serialize_state(state)
	local results = state.results
	if type(results) ~= "string" or results == "" then
		results = "-"
	end
	local line = string.format("%d %s %d %s", state.heartbeat, state.producer, state.sampled, results)
	if state.rtt and #state.rtt > 0 then
		line = line .. " rtt=" .. table.concat(state.rtt, ",")
	end
	if state.web then
		line = line .. string.format(" web=%s,%d,%s", state.web.verdict, state.web.at, state.web.ms or "-")
	end
	if state.check then
		line = line .. string.format(" check=%d", state.check)
	end
	return line .. "\n"
end

local function fresh_window(state, sent_at, size)
	return type(state) ~= "table"
		or type(state.results) ~= "string"
		or state.results == ""
		or (
			type(sent_at) == "number"
			and type(state.sampled) == "number"
			and sent_at - state.sampled > size * M.INTERVAL_SECONDS
		)
end

-- Both append helpers consume the previous state, before sampled is updated.
function M.append_sample(state, sample, sent_at, window_size)
	local size = window_size or M.DEFAULT_WINDOW_SIZE
	if type(sample) == "boolean" then
		sample = sample and "1" or "0"
	end
	assert(sample == "1" or sample == "s" or sample == "0", "invalid ping sample")
	if fresh_window(state, sent_at, size) then
		return sample
	end
	return M.newest(state.results .. sample, size)
end

function M.append_rtt(state, rtt_ms, sent_at, window_size)
	local rtts = {}
	if not fresh_window(state, sent_at, window_size or M.DEFAULT_WINDOW_SIZE) then
		for _, ms in ipairs(state.rtt or {}) do
			table.insert(rtts, ms)
		end
	end
	if type(rtt_ms) == "number" then
		table.insert(rtts, math.floor(rtt_ms + 0.5))
	end
	while #rtts > M.RTT_KEEP do
		table.remove(rtts, 1)
	end
	return #rtts > 0 and rtts or nil
end

function M.summarize(results)
	local summary = { successes = 0, total = 0, trailing_failures = 0, trailing = 0, slow = 0, newest_ok = false }
	local value = tostring(results or "")
	summary.total = #value
	for index = 1, #value do
		local sample = value:sub(index, index)
		if sample == "1" or sample == "s" then
			summary.successes = summary.successes + 1
		end
		if sample == "s" then
			summary.slow = summary.slow + 1
		end
	end
	summary.newest_ok = value:sub(-1) == "1" or value:sub(-1) == "s"
	summary.trailing = #(value:match("0*$") or "")
	summary.trailing_failures = summary.trailing
	return summary
end

function M.upper_median(values)
	if not values or #values == 0 then
		return nil
	end
	local sorted = {}
	for _, value in ipairs(values) do
		table.insert(sorted, value)
	end
	table.sort(sorted)
	return sorted[math.floor(#sorted / 2) + 1]
end

-- First match wins. A web verdict remains current while an on-time recheck
-- runs; a check alone only postpones the pill, never asserts connectivity.
function M.assess(state, now, window_size)
	state = state or {}
	local results = M.newest(state.results, window_size or M.DEFAULT_WINDOW_SIZE)
	local summary = M.summarize(results)
	local checking = state.check ~= nil and now - state.check >= 0 and now - state.check <= M.WEB_CHECK_GRACE_SECONDS
	local web = state.web
	local current = web ~= nil
		and (now - web.at <= M.WEB_FRESH_SECONDS or (checking and state.check - web.at <= M.WEB_FRESH_SECONDS))
	local web_ok = current and web.verdict == "ok"
	local web_bad = current and (web.verdict == "fail" or web.verdict == "portal")
	local assessment =
		{ tier = "stale", summary = summary, web_ok = web_ok, web_bad = web_bad, checking = checking, web = web }
	if results == "" or (type(state.sampled) == "number" and now - state.sampled > M.STALE_SECONDS) then
		return assessment
	end
	local healthy = summary.successes * 10 >= summary.total * 9
	local median = state.rtt and #state.rtt >= M.SLOW_MIN_REPLIES and M.upper_median(state.rtt) or nil
	local ping_slow = median ~= nil and median >= M.SLOW_MS
	local function slow(ms, source)
		assessment.tier = "slow"
		assessment.latency_ms = ms
		assessment.latency_source = source
	end
	if summary.newest_ok then
		if ping_slow then
			slow(median, "ping")
		elseif healthy then
			assessment.tier = "online"
		elseif web_ok then
			assessment.tier = "web"
		else
			assessment.tier = "lossy"
		end
	elseif web_ok then
		if web.ms and web.ms >= M.SLOW_MS then
			slow(web.ms, "web")
		elseif healthy then
			if ping_slow then
				slow(median, "ping")
			else
				assessment.tier = "online"
			end
		else
			assessment.tier = "web"
		end
	elseif summary.trailing >= M.OFFLINE_AFTER_FAILURES and (web_bad or not checking) then
		assessment.tier = "offline"
	else
		assessment.tier = "down"
	end
	return assessment
end

function M.classify(results, sampled, now)
	return M.assess({ results = results, sampled = sampled }, now, M.MAX_WINDOW_SIZE).tier
end

-- Exactly 5 code points, right-aligned with U+2007; the dash for empty.
function M.format_count(summary)
	local text = M.DASH
	if type(summary) == "table" and type(summary.total) == "number" and summary.total > 0 then
		text = string.format("%d/%d", summary.successes or 0, summary.total)
	end
	local width = codepoint_length(text)
	if width >= 5 then
		return text
	end
	return string.rep(FIGURE_SPACE, 5 - width) .. text
end

-- Average RTT in ms from a macOS `ping -n -q` transcript, or nil.
function M.parse_rtt_ms(stdout)
	if type(stdout) ~= "string" then
		return nil
	end
	local avg = stdout:match("round%-trip min/avg/max/stddev = [%d%.]+/([%d%.]+)/[%d%.]+/[%d%.]+ ms")
	if avg == nil then
		return nil
	end
	return tonumber(avg)
end

function M.format_latency(ms)
	local tenths = math.floor((ms + 50) / 100)
	if tenths < 100 then
		return string.format("%d.%ds", math.floor(tenths / 10), tenths % 10)
	end
	return string.format("%ds", math.floor((ms + 500) / 1000))
end

function M.ping_outcome(exit_code, stdout)
	if exit_code == 0 then
		local ms = M.parse_rtt_ms(stdout)
		return ms and ms >= M.SLOW_MS and "s" or "1", ms
	elseif exit_code == 2 then
		return "0", nil
	end
	return nil, "ping " .. (exit_code == nil and "failed to launch" or "exit " .. tostring(exit_code))
end

-- Split on the final curl write-out marker, so a marker in the response body
-- cannot mask the actual HTTP status. Network failures need no response body.
function M.web_outcome(exit_code, stdout, landed_at)
	if exit_code == nil or exit_code == 2 or exit_code == 126 or exit_code == 127 then
		return nil, "curl " .. (exit_code == nil and "failed to launch" or "exit " .. tostring(exit_code))
	end
	local body, code, lookup, connect =
		tostring(stdout or ""):match("^(.*)\n__PING_WINDOW__ (%d%d%d) ([%d%.]+) ([%d%.]+)%s*$")
	lookup, connect = tonumber(lookup), tonumber(connect)
	local ms
	if lookup and connect and connect >= lookup then
		ms = math.floor((connect - lookup) * 1000 + 0.5)
	end
	if exit_code == 0 and (not body or not ms) then
		return nil, "curl output missing valid timing/status trailer"
	end
	local verdict = { at = landed_at, ms = ms, http_code = tonumber(code) }
	if exit_code == 0 then
		verdict.verdict = code == "200" and body:find("Success", 1, true) and "ok" or "portal"
	else
		verdict.verdict = "fail"
		local reasons = { [6] = "DNS lookup failed", [7] = "could not connect", [28] = "timed out" }
		verdict.reason = reasons[exit_code] or "curl exit " .. tostring(exit_code)
	end
	return verdict
end

function M.format_rtt(ms)
	if type(ms) ~= "number" then
		return nil
	end
	if ms < 1 then
		return "<1 ms"
	end
	if math.floor(ms + 0.5) >= 1000 then
		return (M.format_latency(ms):gsub("s$", " s"))
	end
	return string.format("%d ms", math.floor(ms + 0.5))
end

local TIER_GLYPHS = {
	slow = M.GLYPH_OK,
	web = M.GLYPH_OK,
	online = M.GLYPH_OK,
	lossy = M.GLYPH_OK,
	down = M.GLYPH_FAIL,
	offline = M.GLYPH_FAIL,
	stale = M.GLYPH_STALE,
}

local TIER_LABELS = {
	online = "Online",
	lossy = "Packet loss",
	down = "Ping failed",
	offline = "Offline",
}

local function score_text(summary)
	local percent = M.DASH
	if summary.total > 0 then
		percent = string.format("%d%%", math.floor(summary.successes * 100 / summary.total + 0.5))
	end
	return string.format("%d of %d pings answered (%s)", summary.successes, summary.total, percent)
end

local function summary_text(summary)
	return string.format("%s %s last %d s", score_text(summary), MIDDLE_DOT, summary.total * M.INTERVAL_SECONDS)
end

-- Build the menu bar title segments and the lazy dropdown model. opts is
-- { rtt_ms, rtt_sent_at, window_size, web_detail }: persisted RTTs take
-- precedence; legacy RTTs require rtt_sent_at to match the newest sample.
-- A last reply is shown only for a reply sample. window_size clamps the samples
-- (default DEFAULT_WINDOW_SIZE). A perfect (full, all-answered, online)
-- window drops the count from the title. Colors and fonts are the runtime's
-- job: it maps tier plus segment role to hs.styledtext attributes.
-- A full window with every ping answered: the title drops the count.
local function perfect_window(tier, summary, window_size)
	return tier == "online" and summary.total == window_size and summary.successes == summary.total
end

function M.presentation(state_or_nil, now, opts)
	opts = opts or {}
	local window_size = opts.window_size
	if type(window_size) ~= "number" then
		window_size = M.DEFAULT_WINDOW_SIZE
	end
	local results = ""
	local sampled = 0
	if type(state_or_nil) == "table" then
		if type(state_or_nil.results) == "string" then
			results = state_or_nil.results
		end
		if type(state_or_nil.sampled) == "number" then
			sampled = state_or_nil.sampled
		end
	end
	results = M.newest(results, window_size)
	local assessment = M.assess(state_or_nil, now, window_size)
	local summary = assessment.summary
	local tier = assessment.tier
	local glyph = TIER_GLYPHS[tier]
	local count = M.format_count(summary)
	local role = "count"
	if tier == "slow" then
		count = M.format_latency(assessment.latency_ms)
		count = string.rep(FIGURE_SPACE, math.max(0, 5 - codepoint_length(count))) .. count
		role = "latency"
	elseif tier == "web" then
		count = "web"
		role = "note"
	end

	local segments
	local title
	if perfect_window(tier, summary, window_size) then
		segments = {
			{ text = NBSP, role = "pad" },
			{ text = glyph, role = "glyph" },
			{ text = NBSP, role = "pad" },
		}
		title = NBSP .. glyph .. NBSP
	else
		segments = {
			{ text = NBSP, role = "pad" },
			{ text = glyph, role = "glyph" },
			{ text = " ", role = "gap" },
			{ text = count, role = role },
			{ text = NBSP, role = "pad" },
		}
		title = NBSP .. glyph .. " " .. count .. NBSP
	end

	local rtt_ms = nil
	if summary.newest_ok then
		local rtts = state_or_nil and state_or_nil.rtt
		if rtts and #rtts > 0 then
			rtt_ms = rtts[#rtts]
		elseif opts.rtt_sent_at == sampled then
			rtt_ms = opts.rtt_ms
		end
	end

	local detail = summary_text(summary)
	local header_label = TIER_LABELS[tier]
	if tier == "stale" then
		header_label = summary.total > 0 and "No recent pings" or "Waiting for first ping"
	elseif tier == "slow" then
		header_label = "Slow · round trips take " .. M.format_latency(assessment.latency_ms):gsub("s$", " s")
	elseif tier == "web" then
		header_label = summary.successes == 0 and "Online · pings unanswered" or "Online · pings unreliable"
	elseif tier == "down" or tier == "offline" then
		if tier == "down" and assessment.checking then
			header_label = header_label .. " · checking the web…"
		elseif assessment.web_bad then
			if assessment.web.verdict == "portal" then
				header_label = header_label .. " · sign-in required?"
			else
				header_label = header_label
					.. (tier == "offline" and " · web check failed too" or " · web check failed")
			end
		end
	end
	local tooltip = "Internet: " .. header_label:gsub("^%u", string.lower) .. " · " .. score_text(summary)
	if rtt_ms ~= nil then
		tooltip = tooltip .. " · last reply " .. M.format_rtt(rtt_ms)
	end

	local menu = {
		{
			kind = "header",
			segments = {
				{ text = glyph, role = "glyph" },
				{ text = " " .. header_label, role = "label" },
			},
		},
	}

	local history_segments = {}
	for index = 1, window_size do
		local cell = results:sub(index, index)
		if cell == "1" then
			table.insert(history_segments, { text = HISTORY_REPLY, role = "reply" })
		elseif cell == "s" then
			table.insert(history_segments, { text = HISTORY_SLOW, role = "slow" })
		elseif cell == "0" then
			table.insert(history_segments, { text = HISTORY_MISS, role = "miss" })
		else
			table.insert(history_segments, { text = HISTORY_EMPTY, role = "empty" })
		end
	end
	table.insert(history_segments, { text = "  now", role = "now" })
	table.insert(menu, { kind = "history", segments = history_segments })

	table.insert(menu, { kind = "summary", segments = { { text = detail, role = "summary" } } })

	if summary.total > 0 then
		local clock = os.date("%H:%M:%S", sampled)
		local last_text
		if tier == "stale" then
			last_text = "No ping since " .. clock
		elseif not summary.newest_ok then
			last_text = "Last ping failed " .. MIDDLE_DOT .. " " .. clock
		elseif rtt_ms ~= nil then
			last_text = "Last reply " .. M.format_rtt(rtt_ms) .. " " .. MIDDLE_DOT .. " " .. clock
		else
			last_text = "Last ping " .. clock
		end
		table.insert(menu, { kind = "last", segments = { { text = last_text, role = "last" } } })
	end

	local web = assessment.web
	if web and now - web.at <= M.WEB_SHOW_SECONDS then
		local text
		if web.verdict == "ok" then
			text = "Web check OK"
			if web.ms then
				text = text .. " · " .. M.format_rtt(web.ms) .. " round trip"
			end
		elseif web.verdict == "portal" then
			text = "Web check hit a sign-in page"
		else
			text = "Web check failed"
			if opts.web_detail and opts.web_detail.at == web.at and opts.web_detail.reason then
				text = text .. " · " .. opts.web_detail.reason
			end
		end
		text = text .. " · " .. os.date("%H:%M:%S", web.at)
		table.insert(menu, { kind = "web", segments = { { text = text, role = "web" } } })
	end

	table.insert(menu, { kind = "separator", segments = {} })
	table.insert(menu, {
		kind = "info",
		segments = {
			{
				text = "Pinging "
					.. M.TARGET
					.. " every "
					.. M.INTERVAL_SECONDS
					.. " s "
					.. MIDDLE_DOT
					.. " web check when pings fail "
					.. MIDDLE_DOT
					.. " shared with tmux",
				role = "info",
			},
		},
	})
	table.insert(menu, { kind = "separator", segments = {} })
	table.insert(menu, {
		kind = "action",
		segments = { { text = "Network Settings" .. ELLIPSIS, role = "action" } },
		action = "network_settings",
	})
	table.insert(menu, {
		kind = "action",
		segments = { { text = "Copy Diagnostics", role = "action" } },
		action = "copy_diagnostics",
	})

	return {
		tier = tier,
		title = title,
		segments = segments,
		tooltip = tooltip,
		menu = menu,
	}
end

-- Ordered walk-through used by the hidden ⌥ Preview All States action. Each
-- state classifies as the named tier at `now` with the default window size.
function M.preview_states(now)
	local window = M.DEFAULT_WINDOW_SIZE
	local function state(results, extra)
		extra = extra or {}
		return {
			heartbeat = extra.heartbeat or now,
			producer = "hammerspoon",
			sampled = extra.sampled or now,
			results = results,
			rtt = extra.rtt,
			web = extra.web,
			check = extra.check,
		}
	end
	return {
		{ label = "perfect", state = state(string.rep("1", window)) },
		{ label = "count", state = state("0" .. string.rep("1", window - 1)) },
		{ label = "slow", state = state(string.rep("s", 3), { rtt = { 1300, 1400, 1500 } }) },
		{
			label = "web",
			state = state(string.rep("0", window), { web = { verdict = "ok", at = now, ms = 120 } }),
		},
		{ label = "lossy", state = state(string.rep("0", 4) .. string.rep("1", window - 4)) },
		{
			label = "down/checking",
			state = state(string.rep("1", window - 1) .. "0", { check = now }),
		},
		{ label = "offline", state = state(string.rep("0", window)) },
		{
			label = "offline/portal",
			state = state(string.rep("0", window), { web = { verdict = "portal", at = now, ms = 120 } }),
		},
		{
			label = "stale",
			state = state(string.rep("1", window), { sampled = now - M.STALE_SECONDS - 1 }),
		},
	}
end

return M
