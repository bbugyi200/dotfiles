-- Pure ping-window model and presentation for the Hammerspoon ping menu bar.
-- This module is hs-free (only os.date for clock text) so the ping-menubar
-- phase can consume it from the runtime and busted can drive it directly.
local M = {}

-- Shared ping-stream constants. These mirror the constants in
-- `home/bin/executable_tmux_ping` (and vice versa): change both sides
-- together so Hammerspoon and tmux keep rendering the same 20-sample window.
M.TARGET = "8.8.8.8"
M.INTERVAL_SECONDS = 2
M.WINDOW_SIZE = 20
M.WINDOW_SECONDS = 40
M.HANDOFF_SECONDS = 6
M.STALE_SECONDS = 6
M.OFFLINE_AFTER_FAILURES = 3
-- Healthy ratio, 90%: a window ending in a reply is "online" when
-- `successes * 10 >= total * 9`, otherwise "lossy".
M.PING_PATH = "/sbin/ping"
M.PING_ARGS = { "-n", "-q", "-c", "1", "-t", "1", "8.8.8.8" }
M.STATE_BASENAME = "tmux_ping_state"

M.OK_COLOR = "#30d158"
M.WARN_COLOR = "#FF9F0A"
M.ALERT_COLOR = "#E3413B"
M.BADGE_TEXT_COLOR = "#FFFFFF"

M.GLYPH_OK = "✓" -- U+2713, newest ping answered
M.GLYPH_FAIL = "✗" -- U+2717, newest ping missed
M.GLYPH_STALE = "◌" -- U+25CC, no recent pings
M.DASH = "–" -- U+2013, empty-window count

local NBSP = "\194\160" -- U+00A0, menu bar edge pad
local FIGURE_SPACE = "\226\128\135" -- U+2007, fixed-width count pad
local HISTORY_REPLY = "●" -- U+25CF, answered sample cell
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

-- Parse one shared-state line into { heartbeat, producer, sampled, results },
-- with results = "" for "-". Anything the contract calls invalid is nil.
function M.parse_state(text)
	if type(text) ~= "string" or text == "" then
		return nil
	end
	-- Tolerate the single trailing newline writers always emit.
	if text:sub(-1) == "\n" then
		text = text:sub(1, -2)
	end
	local heartbeat, producer, sampled, results = text:match("^(%S+) (%S+) (%S+) (%S+)$")
	if heartbeat == nil then
		return nil
	end
	if producer ~= "hammerspoon" and producer ~= "tmux" then
		return nil
	end
	if not is_digits(heartbeat) or not is_digits(sampled) then
		return nil
	end
	if results == "-" then
		results = ""
	elseif #results < 1 or #results > M.WINDOW_SIZE or results:match("^[01]+$") == nil then
		return nil
	end
	return {
		heartbeat = tonumber(heartbeat),
		producer = producer,
		sampled = tonumber(sampled),
		results = results,
	}
end

-- Render the contract line, including its newline ("-" for an empty window).
function M.serialize_state(state)
	local results = state.results
	if type(results) ~= "string" or results == "" then
		results = "-"
	end
	return string.format("%d %s %d %s\n", state.heartbeat, state.producer, state.sampled, results)
end

-- Append one sample (ok = ping answered) sent at sent_at. A gap longer than
-- WINDOW_SECONDS drops the old window; the result is trimmed to WINDOW_SIZE.
function M.append_sample(state_or_nil, ok, sent_at)
	local sample = ok and "1" or "0"
	if type(state_or_nil) ~= "table" or type(state_or_nil.results) ~= "string" or state_or_nil.results == "" then
		return sample
	end
	if
		type(sent_at) == "number"
		and type(state_or_nil.sampled) == "number"
		and sent_at - state_or_nil.sampled > M.WINDOW_SECONDS
	then
		return sample
	end
	local results = state_or_nil.results .. sample
	if #results > M.WINDOW_SIZE then
		results = results:sub(-M.WINDOW_SIZE)
	end
	return results
end

function M.summarize(results)
	local summary = { successes = 0, total = 0, trailing_failures = 0, newest_ok = false }
	local value = tostring(results or "")
	if #value == 0 then
		return summary
	end
	summary.total = #value
	local successes = 0
	for index = 1, #value do
		if value:sub(index, index) == "1" then
			successes = successes + 1
		end
	end
	summary.successes = successes
	summary.newest_ok = value:sub(-1) == "1"
	local trailing = 0
	for index = #value, 1, -1 do
		if value:sub(index, index) == "0" then
			trailing = trailing + 1
		else
			break
		end
	end
	summary.trailing_failures = trailing
	return summary
end

-- Classify in tier order: stale, offline, down, lossy, online.
function M.classify(results, sampled, now)
	local value = tostring(results or "")
	if value == "" then
		return "stale"
	end
	if type(sampled) == "number" and type(now) == "number" and now - sampled > M.STALE_SECONDS then
		return "stale"
	end
	local summary = M.summarize(value)
	if summary.trailing_failures >= M.OFFLINE_AFTER_FAILURES then
		return "offline"
	end
	if not summary.newest_ok then
		return "down"
	end
	if summary.successes * 10 >= summary.total * 9 then
		return "online"
	end
	return "lossy"
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

function M.format_rtt(ms)
	if type(ms) ~= "number" then
		return nil
	end
	if ms < 1 then
		return "<1 ms"
	end
	return string.format("%d ms", math.floor(ms + 0.5))
end

local TIER_GLYPHS = {
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
-- { rtt_ms, rtt_sent_at }: the RTT shows only when rtt_sent_at equals the
-- newest sampled time. Colors and fonts are the runtime's job: it maps tier
-- plus segment role to hs.styledtext attributes.
function M.presentation(state_or_nil, now, opts)
	opts = opts or {}
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
	local summary = M.summarize(results)
	local tier = M.classify(results, sampled, now)
	local glyph = TIER_GLYPHS[tier]
	local count = M.format_count(summary)

	local segments = {
		{ text = NBSP, role = "pad" },
		{ text = glyph, role = "glyph" },
		{ text = " ", role = "gap" },
		{ text = count, role = "count" },
		{ text = NBSP, role = "pad" },
	}

	local rtt_ms = nil
	if summary.total > 0 and opts.rtt_ms ~= nil and opts.rtt_sent_at == sampled then
		rtt_ms = opts.rtt_ms
	end

	local detail = summary_text(summary)
	local tooltip = "Internet: " .. score_text(summary)
	if rtt_ms ~= nil then
		tooltip = tooltip .. " " .. MIDDLE_DOT .. " last reply " .. M.format_rtt(rtt_ms)
	end

	local header_label = TIER_LABELS[tier]
	if tier == "stale" then
		header_label = summary.total > 0 and "No recent pings" or "Waiting for first ping"
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
	for index = 1, M.WINDOW_SIZE do
		local cell = results:sub(index, index)
		if cell == "1" then
			table.insert(history_segments, { text = HISTORY_REPLY, role = "reply" })
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

	return {
		tier = tier,
		title = NBSP .. glyph .. " " .. count .. NBSP,
		segments = segments,
		tooltip = tooltip,
		menu = menu,
	}
end

return M
