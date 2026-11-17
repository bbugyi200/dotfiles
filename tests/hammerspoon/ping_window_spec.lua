local PING_WINDOW_PATH = "home/dot_hammerspoon/ping_window.lua"

local ping_window = assert(loadfile(PING_WINDOW_PATH))()

local NBSP = "\194\160" -- U+00A0
local FIGURE_SPACE = "\226\128\135" -- U+2007

local FIXTURES = {
	"1759680002 hammerspoon 1759680002 11111111111111111111",
	"1759680010 hammerspoon 1759680002 11111111111111111111",
	"1759680004 tmux 1759680004 0111",
	"1759680000 hammerspoon 0 -",
}

local SUCCESS_TRANSCRIPT = table.concat({
	"PING 8.8.8.8 (8.8.8.8): 56 data bytes",
	"64 bytes from 8.8.8.8: icmp_seq=0 ttl=117 time=18.345 ms",
	"",
	"--- 8.8.8.8 ping statistics ---",
	"1 packets transmitted, 1 packets received, 0.0% packet loss",
	"round-trip min/avg/max/stddev = 18.123/18.345/18.567/0.222 ms",
	"",
}, "\n")

local TIMEOUT_TRANSCRIPT = table.concat({
	"PING 8.8.8.8 (8.8.8.8): 56 data bytes",
	"",
	"--- 8.8.8.8 ping statistics ---",
	"1 packets transmitted, 0 packets received, 100.0% packet loss",
	"",
}, "\n")

local function codepoint_length(text)
	local count = 0
	for index = 1, #text do
		local byte = text:byte(index)
		if byte < 128 or byte >= 192 then
			count = count + 1
		end
	end
	return count
end

local function concat_segments(segments)
	local parts = {}
	for _, segment in ipairs(segments) do
		table.insert(parts, segment.text)
	end
	return table.concat(parts)
end

local function segment_roles(segments)
	local roles = {}
	for _, segment in ipairs(segments) do
		table.insert(roles, segment.role)
	end
	return roles
end

local function menu_kinds(menu)
	local kinds = {}
	for _, row in ipairs(menu) do
		table.insert(kinds, row.kind)
	end
	return kinds
end

local function find_row(menu, kind)
	for _, row in ipairs(menu) do
		if row.kind == kind then
			return row
		end
	end
	return nil
end

describe("Hammerspoon ping window shared constants", function()
	it("matches the tmux_ping contract values", function()
		assert.equals("8.8.8.8", ping_window.TARGET)
		assert.equals(2, ping_window.INTERVAL_SECONDS)
		assert.equals(30, ping_window.DEFAULT_WINDOW_SIZE)
		assert.equals(3, ping_window.MIN_WINDOW_SIZE)
		assert.equals(99, ping_window.MAX_WINDOW_SIZE)
		assert.equals(".config/ping_window/config", ping_window.CONFIG_RELATIVE_PATH)
		assert.equals(6, ping_window.HANDOFF_SECONDS)
		assert.equals(6, ping_window.STALE_SECONDS)
		assert.equals(3, ping_window.OFFLINE_AFTER_FAILURES)
		assert.equals("/sbin/ping", ping_window.PING_PATH)
		assert.same({ "-n", "-q", "-c", "1", "-W", "500", "8.8.8.8" }, ping_window.PING_ARGS)
		assert.equals("tmux_ping_state", ping_window.STATE_BASENAME)
		assert.equals("#30d158", ping_window.OK_COLOR)
		assert.equals("#FF9F0A", ping_window.WARN_COLOR)
		assert.equals("#E3413B", ping_window.ALERT_COLOR)
		assert.equals("#FFFFFF", ping_window.BADGE_TEXT_COLOR)
	end)

	it("mirrors the tmux_ping readonly constants", function()
		local handle = assert(io.open("home/bin/executable_tmux_ping", "r"))
		local text = assert(handle:read("*a"))
		handle:close()
		local function readonly_value(name)
			local pattern = "readonly " .. name .. "=([^\n]*)"
			local raw = text:match(pattern)
			assert.is_not_nil(raw, "missing readonly " .. name)
			raw = raw:match("^[ \t]*['\"]?(.-)['\"]?[ \t]*$")
			return raw
		end
		assert.equals(tostring(ping_window.INTERVAL_SECONDS), readonly_value("INTERVAL_SECONDS"))
		assert.equals(tostring(ping_window.DEFAULT_WINDOW_SIZE), readonly_value("DEFAULT_WINDOW_SIZE"))
		assert.equals(tostring(ping_window.MIN_WINDOW_SIZE), readonly_value("MIN_WINDOW_SIZE"))
		assert.equals(tostring(ping_window.MAX_WINDOW_SIZE), readonly_value("MAX_WINDOW_SIZE"))
		assert.equals(ping_window.CONFIG_RELATIVE_PATH, readonly_value("CONFIG_RELATIVE_PATH"))
		assert.equals(tostring(ping_window.SLOW_MS), readonly_value("SLOW_MS"))
		assert.equals(tostring(ping_window.RTT_KEEP), readonly_value("RTT_KEEP"))
		assert.equals(tostring(ping_window.SLOW_MIN_REPLIES), readonly_value("SLOW_MIN_REPLIES"))
		assert.equals(tostring(ping_window.PING_WAIT_MS), readonly_value("PING_WAIT_MS"))
		assert.equals(tostring(ping_window.WEB_FRESH_SECONDS), readonly_value("WEB_FRESH_SECONDS"))
		assert.equals(tostring(ping_window.WEB_CHECK_GRACE_SECONDS), readonly_value("WEB_CHECK_GRACE_SECONDS"))
		assert.equals("-W", ping_window.PING_ARGS[5])
		assert.equals(tostring(ping_window.PING_WAIT_MS), ping_window.PING_ARGS[6])
		assert.is_not_nil(
			text:find('ping %-n %-q %-c 1 %-W "%$%{PING_WAIT_MS}"', 1, false),
			"tmux pinger must use PING_WAIT_MS with -W"
		)
	end)
end)

describe("Hammerspoon ping window config parsing", function()
	it("resolves the shared fixture table", function()
		local cases = {
			{ text = nil, window = 30 },
			{ text = "", window = 30 },
			{ text = "window_size=20\n", window = 20 },
			{ text = "  window_size = 45  \r\n", window = 45 },
			{ text = "# window_size=10\nwindow_size=12\n", window = 12 },
			{ text = "window_size=20\nwindow_size=25\n", window = 25 },
			{ text = "other=1\nwindow_size=99", window = 99 },
			{ text = "window_size=3", window = 3 },
			{ text = "window_size=2", window = 30 },
			{ text = "window_size=0", window = 30 },
			{ text = "window_size=100", window = 30 },
			{ text = "window_size=-5", window = 30 },
			{ text = "window_size=030", window = 30 },
			{ text = "window_size=abc", window = 30 },
			{ text = "window_size=", window = 30 },
			{ text = "window_size=20 #x", window = 30 },
		}
		for _, case in ipairs(cases) do
			local window = ping_window.parse_config(case.text)
			assert.equals(case.window, window, "text: " .. tostring(case.text))
		end
	end)

	it("reports a problem only for present-but-invalid values", function()
		local _, no_problem = ping_window.parse_config(nil)
		assert.is_nil(no_problem)
		local _, empty_problem = ping_window.parse_config("")
		assert.is_nil(empty_problem)
		local _, missing_problem = ping_window.parse_config("other=1\n")
		assert.is_nil(missing_problem)
		local window, valid_problem = ping_window.parse_config("window_size=20\n")
		assert.equals(20, window)
		assert.is_nil(valid_problem)
		local fallback, invalid_problem = ping_window.parse_config("window_size=abc\n")
		assert.equals(30, fallback)
		assert.equals("invalid window_size 'abc'; using 30", invalid_problem)
		local _, last_invalid = ping_window.parse_config("window_size=20\nwindow_size=abc\n")
		assert.is_not_nil(last_invalid)
	end)
end)

describe("Hammerspoon ping window state parsing", function()
	it("parses all four shared contract fixtures", function()
		local first = ping_window.parse_state(FIXTURES[1])
		assert.same(
			{ heartbeat = 1759680002, producer = "hammerspoon", sampled = 1759680002, results = string.rep("1", 20) },
			first
		)

		local paused = ping_window.parse_state(FIXTURES[2])
		assert.same(
			{ heartbeat = 1759680010, producer = "hammerspoon", sampled = 1759680002, results = string.rep("1", 20) },
			paused
		)

		local tmux = ping_window.parse_state(FIXTURES[3])
		assert.same({ heartbeat = 1759680004, producer = "tmux", sampled = 1759680004, results = "0111" }, tmux)

		local empty = ping_window.parse_state(FIXTURES[4])
		assert.same({ heartbeat = 1759680000, producer = "hammerspoon", sampled = 0, results = "" }, empty)
	end)

	it("tolerates one trailing newline", function()
		for _, fixture in ipairs(FIXTURES) do
			assert.same(ping_window.parse_state(fixture), ping_window.parse_state(fixture .. "\n"))
		end
	end)

	it("rejects every invalid form as no state", function()
		assert.is_nil(ping_window.parse_state(nil))
		local invalid = {
			"",
			"\n",
			"1759680002 hammerspoon 1759680002",
			"1759680002 hammerspoon 1759680002 11 extra",
			"1759680002 cron 1759680002 11",
			"1759680002 HAMMERSPOON 1759680002 11",
			"abc hammerspoon 1759680002 11",
			"1759680002 hammerspoon xyz 11",
			"-5 hammerspoon 1759680002 11",
			"1759680002 hammerspoon 1759680002",
			"1759680002 hammerspoon 1759680002 ",
			"1759680002 hammerspoon 1759680002 2",
			"1759680002 hammerspoon 1759680002 112a1",
			"1759680002 hammerspoon 1759680002 " .. string.rep("1", 100),
			" 1759680002 hammerspoon 1759680002 11",
			"1759680002  hammerspoon 1759680002 11",
			"1759680002 hammerspoon 1759680002 11 ",
			"1759680002 hammerspoon 1759680002 11\n\n",
			"1759680002\thammerspoon\t1759680002\t11",
		}
		for _, text in ipairs(invalid) do
			assert.is_nil(ping_window.parse_state(text), "expected nil for " .. tostring(text))
		end
	end)

	it("accepts a 99-character window", function()
		local line = "1759680002 hammerspoon 1759680002 " .. string.rep("1", 99)
		local parsed = assert(ping_window.parse_state(line))
		assert.equals(string.rep("1", 99), parsed.results)
	end)

	it("round trips serialize and parse", function()
		for _, fixture in ipairs(FIXTURES) do
			assert.equals(fixture .. "\n", ping_window.serialize_state(ping_window.parse_state(fixture)))
		end
		local state = { heartbeat = 1759680004, producer = "tmux", sampled = 1759680004, results = "0111" }
		assert.equals("1759680004 tmux 1759680004 0111\n", ping_window.serialize_state(state))
		assert.equals(
			"1759680000 hammerspoon 0 -\n",
			ping_window.serialize_state({ heartbeat = 1759680000, producer = "hammerspoon", sampled = 0, results = "" })
		)
	end)
end)

describe("Hammerspoon ping window append", function()
	it("starts a fresh window from nil or an empty window", function()
		assert.equals("1", ping_window.append_sample(nil, true, 1759680002))
		assert.equals("0", ping_window.append_sample(nil, false, 1759680002))
		local empty = { heartbeat = 1759680000, producer = "hammerspoon", sampled = 0, results = "" }
		assert.equals("1", ping_window.append_sample(empty, true, 1759680002))
	end)

	it("appends inside the gap window and resets past it", function()
		local state = { heartbeat = 100, producer = "tmux", sampled = 100, results = "11" }
		assert.equals("111", ping_window.append_sample(state, true, 160))
		assert.equals("110", ping_window.append_sample(state, false, 160))
		assert.equals("1", ping_window.append_sample(state, true, 161))
		assert.equals("0", ping_window.append_sample(state, false, 161))
	end)

	it("derives the gap threshold from the window size", function()
		local state = { heartbeat = 100, producer = "tmux", sampled = 100, results = "11" }
		assert.equals("111", ping_window.append_sample(state, true, 140, 20))
		assert.equals("1", ping_window.append_sample(state, true, 141, 20))
	end)

	it("trims to the newest 30 samples by default", function()
		local state = { heartbeat = 100, producer = "tmux", sampled = 100, results = "0" .. string.rep("1", 29) }
		assert.equals(string.rep("1", 30), ping_window.append_sample(state, true, 101))
		assert.equals(string.rep("1", 29) .. "0", ping_window.append_sample(state, false, 101))
	end)

	it("trims to the configured window size", function()
		local state = { heartbeat = 100, producer = "tmux", sampled = 100, results = string.rep("1", 30) }
		assert.equals(string.rep("1", 20), ping_window.append_sample(state, true, 101, 20))
	end)
end)

describe("Hammerspoon ping window summarize and classify", function()
	it("summarizes mixed windows", function()
		assert.same(
			{ successes = 2, total = 5, trailing_failures = 2, trailing = 2, slow = 0, newest_ok = false },
			ping_window.summarize("01100")
		)
		assert.same(
			{ successes = 4, total = 5, trailing_failures = 0, trailing = 0, slow = 0, newest_ok = true },
			ping_window.summarize("01111")
		)
		assert.same(
			{ successes = 0, total = 0, trailing_failures = 0, trailing = 0, slow = 0, newest_ok = false },
			ping_window.summarize("")
		)
	end)

	it("splits online and lossy at 90 percent", function()
		local now = 1759680010
		assert.equals("online", ping_window.classify("0" .. string.rep("1", 17) .. "01", now, now))
		assert.equals("lossy", ping_window.classify("00" .. string.rep("1", 16) .. "01", now, now))
	end)

	it("escalates down to offline at three trailing misses", function()
		local now = 1759680010
		assert.equals("down", ping_window.classify(string.rep("1", 18) .. "00", now, now))
		assert.equals("offline", ping_window.classify(string.rep("1", 17) .. "000", now, now))
		assert.equals("offline", ping_window.classify(string.rep("0", 20), now, now))
	end)

	it("treats a window older than 6 seconds as stale", function()
		local now = 1759680010
		assert.equals("online", ping_window.classify(string.rep("1", 20), now - 6, now))
		assert.equals("stale", ping_window.classify(string.rep("1", 20), now - 7, now))
		assert.equals("stale", ping_window.classify(string.rep("1", 20), 1759680002, 1759680010))
		assert.equals("stale", ping_window.classify("", now, now))
	end)
end)

describe("Hammerspoon ping window count and RTT", function()
	it("right-aligns every count to exactly 5 code points", function()
		assert.equals("30/30", ping_window.format_count({ successes = 30, total = 30 }))
		assert.equals("99/99", ping_window.format_count({ successes = 99, total = 99 }))
		assert.equals(FIGURE_SPACE .. "9/20", ping_window.format_count({ successes = 9, total = 20 }))
		assert.equals(FIGURE_SPACE .. FIGURE_SPACE .. "1/1", ping_window.format_count({ successes = 1, total = 1 }))
		assert.equals(
			FIGURE_SPACE .. FIGURE_SPACE .. FIGURE_SPACE .. FIGURE_SPACE .. "–",
			ping_window.format_count({ successes = 0, total = 0 })
		)
		for total = 0, 99 do
			for _, successes in ipairs({ 0, math.floor(total / 2), total }) do
				if successes <= total then
					assert.equals(
						5,
						codepoint_length(ping_window.format_count({ successes = successes, total = total }))
					)
				end
			end
		end
	end)

	it("parses the RTT from a real macOS success transcript", function()
		assert.equals(18.345, ping_window.parse_rtt_ms(SUCCESS_TRANSCRIPT))
	end)

	it("returns nil RTT for a timeout transcript", function()
		assert.is_nil(ping_window.parse_rtt_ms(TIMEOUT_TRANSCRIPT))
		assert.is_nil(ping_window.parse_rtt_ms("not ping output"))
		assert.is_nil(ping_window.parse_rtt_ms(nil))
	end)

	it("formats RTT values", function()
		assert.equals("18 ms", ping_window.format_rtt(18.345))
		assert.equals("19 ms", ping_window.format_rtt(18.5))
		assert.equals("1 ms", ping_window.format_rtt(1))
		assert.equals("<1 ms", ping_window.format_rtt(0.999))
		assert.equals("<1 ms", ping_window.format_rtt(0))
	end)
end)

describe("Hammerspoon ping window presentation", function()
	it("builds the exact title string and segment roles for each tier", function()
		local now = 1759680010
		local full_roles = { "pad", "glyph", "gap", "count", "pad" }
		local perfect_roles = { "pad", "glyph", "pad" }
		local cases = {
			{
				results = string.rep("1", 30),
				sampled = now,
				tier = "online",
				title = NBSP .. "✓" .. NBSP,
				roles = perfect_roles,
			},
			{
				results = "0" .. string.rep("1", 29),
				sampled = now,
				tier = "online",
				title = NBSP .. "✓" .. " " .. "29/30" .. NBSP,
				roles = full_roles,
			},
			{
				results = "000" .. string.rep("1", 25) .. "01",
				sampled = now,
				tier = "lossy",
				title = NBSP .. "✓" .. " " .. "26/30" .. NBSP,
				roles = full_roles,
			},
			{
				results = string.rep("1", 29) .. "0",
				sampled = now,
				tier = "down",
				title = NBSP .. "✗" .. " " .. "29/30" .. NBSP,
				roles = full_roles,
			},
			{
				results = string.rep("1", 27) .. "000",
				sampled = now,
				tier = "offline",
				title = NBSP .. "✗" .. " " .. "27/30" .. NBSP,
				roles = full_roles,
			},
			{
				results = string.rep("1", 30),
				sampled = now - 7,
				tier = "stale",
				title = NBSP .. "◌" .. " " .. "30/30" .. NBSP,
				roles = full_roles,
			},
		}
		for _, case in ipairs(cases) do
			local state = { heartbeat = now, producer = "hammerspoon", sampled = case.sampled, results = case.results }
			local presentation =
				ping_window.presentation(ping_window.parse_state(ping_window.serialize_state(state)), now, {})
			assert.equals(case.tier, presentation.tier)
			assert.equals(case.title, presentation.title)
			assert.same(case.roles, segment_roles(presentation.segments))
			assert.equals(presentation.title, concat_segments(presentation.segments))
		end
	end)

	it("keeps the count while the window is still filling", function()
		local now = 1759680010
		local filling = { heartbeat = now, producer = "hammerspoon", sampled = now, results = string.rep("1", 29) }
		local presentation = ping_window.presentation(filling, now, {})
		assert.equals("online", presentation.tier)
		assert.equals(NBSP .. "✓" .. " " .. "29/29" .. NBSP, presentation.title)
		assert.same({ "pad", "glyph", "gap", "count", "pad" }, segment_roles(presentation.segments))
		assert.equals(presentation.title, concat_segments(presentation.segments))

		local small = { heartbeat = now, producer = "hammerspoon", sampled = now, results = string.rep("1", 19) }
		local small_presentation = ping_window.presentation(small, now, { window_size = 20 })
		assert.equals("online", small_presentation.tier)
		assert.equals(NBSP .. "✓" .. " " .. "19/19" .. NBSP, small_presentation.title)
		assert.same({ "pad", "glyph", "gap", "count", "pad" }, segment_roles(small_presentation.segments))
		assert.equals(small_presentation.title, concat_segments(small_presentation.segments))
	end)

	it("keeps the tooltip and dropdown for a perfect window", function()
		local now = 1759680010
		local state = { heartbeat = now, producer = "hammerspoon", sampled = now, results = string.rep("1", 30) }
		local presentation =
			ping_window.presentation(ping_window.parse_state(ping_window.serialize_state(state)), now, {})
		assert.equals(NBSP .. "✓" .. NBSP, presentation.title)
		assert.equals("Internet: online · 30 of 30 pings answered (100%)", presentation.tooltip)
		local header = find_row(presentation.menu, "header")
		assert.equals("✓ Online", concat_segments(header.segments))
		local summary = find_row(presentation.menu, "summary")
		assert.equals("30 of 30 pings answered (100%) · last 60 s", concat_segments(summary.segments))
	end)

	it("renders an empty window with a dashed count", function()
		local presentation = ping_window.presentation(nil, 1759680010, {})
		assert.equals("stale", presentation.tier)
		local count = FIGURE_SPACE .. FIGURE_SPACE .. FIGURE_SPACE .. FIGURE_SPACE .. "–"
		assert.equals(NBSP .. "◌" .. " " .. count .. NBSP, presentation.title)
	end)

	it("labels each header row", function()
		local now = 1759680010
		local cases = {
			{ results = string.rep("1", 30), sampled = now, label = "Online", glyph = "✓" },
			{ results = "000" .. string.rep("1", 25) .. "01", sampled = now, label = "Packet loss", glyph = "✓" },
			{ results = string.rep("1", 29) .. "0", sampled = now, label = "Ping failed", glyph = "✗" },
			{ results = string.rep("1", 27) .. "000", sampled = now, label = "Offline", glyph = "✗" },
			{ results = string.rep("1", 30), sampled = now - 7, label = "No recent pings", glyph = "◌" },
		}
		for _, case in ipairs(cases) do
			local state = { heartbeat = now, producer = "hammerspoon", sampled = case.sampled, results = case.results }
			local header = find_row(ping_window.presentation(state, now, {}).menu, "header")
			assert.equals(case.glyph .. " " .. case.label, concat_segments(header.segments))
			assert.same({ "glyph", "label" }, segment_roles(header.segments))
		end
		local waiting = find_row(ping_window.presentation(nil, now, {}).menu, "header")
		assert.equals("◌ Waiting for first ping", concat_segments(waiting.segments))
	end)

	it("draws the history strip oldest-first with unfilled slots", function()
		local now = 1759680010
		local state = { heartbeat = now, producer = "tmux", sampled = now, results = "0111" }
		local history = find_row(ping_window.presentation(state, now, {}).menu, "history")
		assert.equals(31, #history.segments)
		assert.equals("○●●●" .. string.rep("·", 26) .. "  now", concat_segments(history.segments))
		local roles = segment_roles(history.segments)
		assert.same("miss", roles[1])
		assert.same("reply", roles[2])
		assert.same("empty", roles[5])
		assert.same("now", roles[31])

		local full = { heartbeat = now, producer = "hammerspoon", sampled = now, results = "01" .. string.rep("1", 28) }
		local full_history = find_row(ping_window.presentation(full, now, {}).menu, "history")
		assert.equals("○●" .. string.rep("●", 28) .. "  now", concat_segments(full_history.segments))
	end)

	it("sizes the history strip from the window_size option", function()
		local now = 1759680010
		local state = { heartbeat = now, producer = "tmux", sampled = now, results = "0111" }
		local default_history = find_row(ping_window.presentation(state, now, {}).menu, "history")
		assert.equals(31, #default_history.segments)
		local sized = find_row(ping_window.presentation(state, now, { window_size = 20 }).menu, "history")
		assert.equals(21, #sized.segments)
		assert.equals("○●●●" .. string.rep("·", 16) .. "  now", concat_segments(sized.segments))
	end)

	it("clamps a larger window to the configured size", function()
		local now = 1759680010
		local state = { heartbeat = now, producer = "hammerspoon", sampled = now, results = string.rep("1", 30) }
		local presentation = ping_window.presentation(state, now, { window_size = 20 })
		assert.equals(NBSP .. "✓" .. NBSP, presentation.title)
		local summary = find_row(presentation.menu, "summary")
		assert.equals("20 of 20 pings answered (100%) · last 40 s", concat_segments(summary.segments))
	end)

	it("summarizes the window and spans total times two seconds", function()
		local now = 1759680010
		local state = { heartbeat = now, producer = "hammerspoon", sampled = now, results = string.rep("1", 30) }
		local summary = find_row(ping_window.presentation(state, now, {}).menu, "summary")
		assert.equals("30 of 30 pings answered (100%) · last 60 s", concat_segments(summary.segments))
		local empty_summary = find_row(ping_window.presentation(nil, now, {}).menu, "summary")
		assert.equals("0 of 0 pings answered (–) · last 0 s", concat_segments(empty_summary.segments))
	end)

	it("covers all four last-ping variants", function()
		local now = 1759680010
		local sampled = now
		local clock = os.date("%H:%M:%S", sampled)
		local reply = { heartbeat = now, producer = "hammerspoon", sampled = sampled, results = string.rep("1", 30) }
		local with_rtt =
			find_row(ping_window.presentation(reply, now, { rtt_ms = 18.345, rtt_sent_at = sampled }).menu, "last")
		assert.equals("Last reply 18 ms · " .. clock, concat_segments(with_rtt.segments))
		local unknown_rtt = find_row(ping_window.presentation(reply, now, {}).menu, "last")
		assert.equals("Last ping " .. clock, concat_segments(unknown_rtt.segments))
		local failed =
			{ heartbeat = now, producer = "hammerspoon", sampled = sampled, results = string.rep("1", 29) .. "0" }
		local failed_row = find_row(ping_window.presentation(failed, now, {}).menu, "last")
		assert.equals("Last ping failed · " .. clock, concat_segments(failed_row.segments))
		local stale_state =
			{ heartbeat = now, producer = "hammerspoon", sampled = now - 30, results = string.rep("1", 30) }
		local stale_row = find_row(ping_window.presentation(stale_state, now, {}).menu, "last")
		assert.equals("No ping since " .. os.date("%H:%M:%S", now - 30), concat_segments(stale_row.segments))
		assert.is_nil(find_row(ping_window.presentation(nil, now, {}).menu, "last"))
	end)

	it("shows the RTT in the tooltip only for the newest sample", function()
		local now = 1759680010
		local state =
			{ heartbeat = now, producer = "hammerspoon", sampled = now, results = "000" .. string.rep("1", 25) .. "01" }
		assert.equals(
			"Internet: packet loss · 26 of 30 pings answered (87%) · last reply 18 ms",
			ping_window.presentation(state, now, { rtt_ms = 18.345, rtt_sent_at = now }).tooltip
		)
		assert.equals(
			"Internet: packet loss · 26 of 30 pings answered (87%)",
			ping_window.presentation(state, now, {}).tooltip
		)
		assert.equals(
			"Internet: packet loss · 26 of 30 pings answered (87%)",
			ping_window.presentation(state, now, { rtt_ms = 18.345, rtt_sent_at = now - 2 }).tooltip
		)
	end)

	it("orders menu rows with separators and a network settings action", function()
		local now = 1759680010
		local state = { heartbeat = now, producer = "hammerspoon", sampled = now, results = string.rep("1", 30) }
		local menu = ping_window.presentation(state, now, {}).menu
		assert.same(
			{ "header", "history", "summary", "last", "separator", "info", "separator", "action" },
			menu_kinds(menu)
		)
		assert.same(
			{ "header", "history", "summary", "separator", "info", "separator", "action" },
			menu_kinds(ping_window.presentation(nil, now, {}).menu)
		)
		local info = find_row(menu, "info")
		assert.equals(
			"Pinging 8.8.8.8 every 2 s · web check when pings fail · shared with tmux",
			concat_segments(info.segments)
		)
		local action = find_row(menu, "action")
		assert.equals("Network Settings…", concat_segments(action.segments))
		assert.equals("network_settings", action.action)
	end)
end)

describe("ping state v2 contract", function()
	it("pins the constants consumed by the later tmux and producer phases", function()
		for key, value in pairs({
			SLOW_MS = 500,
			RTT_KEEP = 5,
			SLOW_MIN_REPLIES = 3,
			PING_WAIT_MS = 500,
			WEB_FRESH_SECONDS = 15,
			WEB_CHECK_GRACE_SECONDS = 10,
			WEB_TIMEOUT_SECONDS = 8,
			WEB_CONNECT_TIMEOUT_SECONDS = 6,
			WEB_RECHECK_SECONDS = 10,
			WEB_SHOW_SECONDS = 300,
			EVENTS_MAX_LINES = 2000,
			EVENTS_KEEP_LINES = 1000,
		}) do
			assert.equals(value, ping_window[key], key)
		end
		assert.equals(
			ping_window.WEB_TIMEOUT_SECONDS + ping_window.INTERVAL_SECONDS,
			ping_window.WEB_CHECK_GRACE_SECONDS
		)
		assert.equals("ping_window_events.tsv", ping_window.EVENTS_BASENAME)
		assert.equals("/usr/bin/curl", ping_window.CURL_PATH)
		assert.same({
			"-sS",
			"--max-time",
			"8",
			"--connect-timeout",
			"6",
			"--max-redirs",
			"0",
			"--noproxy",
			"*",
			"-w",
			"\n__PING_WINDOW__ %{http_code} %{time_namelookup} %{time_connect}",
			"http://captive.apple.com/hotspot-detect.html",
		}, ping_window.CURL_ARGS)
		assert.equals(ping_window.WEB_URL, ping_window.CURL_ARGS[#ping_window.CURL_ARGS])
	end)

	it("round trips tokens in canonical order and preserves v1 table shapes", function()
		local state = ping_window.parse_state("1000 tmux 998 1s0 check=999 ignored= rtt=1,1400 web=ok,995,0")
		assert.same({
			heartbeat = 1000,
			producer = "tmux",
			sampled = 998,
			results = "1s0",
			rtt = { 1, 1400 },
			web = { verdict = "ok", at = 995, ms = 0 },
			check = 999,
		}, state)
		local line = "1000 tmux 998 1s0 rtt=1,1400 web=ok,995,0 check=999\n"
		assert.equals(line, ping_window.serialize_state(state))
		assert.same(state, ping_window.parse_state(line))
		for _, token in ipairs({ "web=fail,995,-", "web=portal,995,120", "rtt=0,1,2,3,999999", "check=0" }) do
			local raw = "1000 hammerspoon 0 - " .. token .. "\n"
			assert.equals(raw, ping_window.serialize_state(ping_window.parse_state(raw)))
		end
		local v1 = ping_window.parse_state("1000 hammerspoon 998 111")
		assert.is_nil(v1.rtt)
		assert.is_nil(v1.web)
		assert.is_nil(v1.check)
	end)

	it("ignores malformed known values without invalidating the line", function()
		local values = {
			rtt = { "", ",", "1,", ",1", "1,,2", "-1", "1.2", "1000000", "1,2,3,4,5,6", "a" },
			web = { "", "OK,1,2", "no,1,2", "ok,x,2", "ok,1,x", "ok,-1,2", "ok,1,-2", "ok,1,1.2", "ok,1,", "ok,1,2,3" },
			check = { "", "-1", "1.2", "x", "1,2" },
		}
		for key, invalid in pairs(values) do
			for _, value in ipairs(invalid) do
				local state = assert(ping_window.parse_state("1000 hammerspoon 1000 111 " .. key .. "=" .. value))
				assert.is_nil(state[key], key .. "=" .. value)
				assert.equals("111", state.results)
			end
		end
	end)

	it("uses the last duplicate including an invalid last value", function()
		local base = "1000 hammerspoon 1000 s "
		local state = ping_window.parse_state(base .. "rtt=1 rtt=500 web=fail,1,- web=ok,2,0 check=1 check=2")
		assert.same({ 500 }, state.rtt)
		assert.same({ verdict = "ok", at = 2, ms = 0 }, state.web)
		assert.equals(2, state.check)
		state = ping_window.parse_state(base .. "rtt=1 rtt= web=ok,1,2 web=bad check=1 check=x")
		assert.is_nil(state.rtt)
		assert.is_nil(state.web)
		assert.is_nil(state.check)
	end)

	it("rejects malformed extension grammar, whitespace, and base fields", function()
		local base = "1000 hammerspoon 1000 1s0"
		for _, suffix in ipairs({
			" ",
			"  rtt=1",
			"\trtt=1",
			" extra",
			" 1key=x",
			" X=x",
			" _key=x",
			" foo-bar=x",
			" foo=x ",
			" foo=x\tbar=y",
			" foo=x\nbar=y",
			" foo=x\r\n",
		}) do
			assert.is_nil(ping_window.parse_state(base .. suffix), suffix)
		end
		assert.is_nil(ping_window.parse_state("1000 hammerspoon 1000 " .. string.rep("s", 100)))
		assert.is_not_nil(ping_window.parse_state("1000 hammerspoon 1000 " .. string.rep("s", 99)))
	end)

	it("appends literal samples and RTTs with the same gap boundary without mutating state", function()
		local state = { sampled = 100, results = "1s0", rtt = { 10, 20, 30, 40, 50 } }
		assert.equals("s0s", ping_window.append_sample(state, "s", 106, 3))
		assert.equals("s00", ping_window.append_sample(state, "0", 106, 3))
		assert.equals("s01", ping_window.append_sample(state, "1", 106, 3))
		assert.same({ 20, 30, 40, 50, 501 }, ping_window.append_rtt(state, 500.5, 106, 3))
		assert.same(state.rtt, ping_window.append_rtt(state, nil, 106, 3))
		assert.equals("s", ping_window.append_sample(state, "s", 107, 3))
		assert.same({ 501 }, ping_window.append_rtt(state, 500.5, 107, 3))
		assert.is_nil(ping_window.append_rtt(state, nil, 107, 3))
		assert.same({ 10, 20, 30, 40, 50 }, state.rtt)
		assert.same({ 0 }, ping_window.append_rtt(nil, 0.4, 100))
		assert.is_nil(ping_window.append_rtt({ results = "", rtt = { 10 } }, nil, 100))
	end)

	it("counts slow replies and computes the upper median on a copy", function()
		assert.same(
			{ successes = 3, slow = 2, total = 6, trailing = 2, trailing_failures = 2, newest_ok = false },
			ping_window.summarize("01ss00")
		)
		assert.is_true(ping_window.summarize("s").newest_ok)
		local rtts = { 1400, 20, 2000, 21 }
		assert.equals(1400, ping_window.upper_median(rtts))
		assert.same({ 1400, 20, 2000, 21 }, rtts)
		assert.equals(20, ping_window.upper_median({ 30, 10, 20 }))
		assert.is_nil(ping_window.upper_median({}))
		assert.is_nil(ping_window.upper_median(nil))
	end)

	it("formats latency rounding boundaries and RTT seconds", function()
		for _, case in ipairs({
			{ 500, "0.5s" },
			{ 1449, "1.4s" },
			{ 1450, "1.5s" },
			{ 9949, "9.9s" },
			{ 9950, "10s" },
			{ 10499, "10s" },
			{ 10500, "11s" },
			{ 999999, "1000s" },
		}) do
			assert.equals(case[2], ping_window.format_latency(case[1]))
		end
		assert.equals("999 ms", ping_window.format_rtt(999.4))
		assert.equals("1.0 s", ping_window.format_rtt(999.5))
		assert.equals("1.4 s", ping_window.format_rtt(1400))
		assert.equals("10 s", ping_window.format_rtt(9950))
		assert.is_nil(ping_window.format_rtt(nil))
	end)

	it("interprets macOS ping replies, timeouts, and tool failures separately", function()
		local sample, ms = ping_window.ping_outcome(0, SUCCESS_TRANSCRIPT)
		assert.equals("1", sample)
		assert.equals(18.345, ms)
		local slow_transcript = "PING 8.8.8.8 (8.8.8.8): 56 data bytes\n\n--- 8.8.8.8 ping statistics ---\n"
			.. "1 packets transmitted, 1 packets received, 0.0% packet loss\n"
			.. "round-trip min/avg/max/stddev = 1400.123/1400.123/1400.123/0.000 ms\n"
		sample, ms = ping_window.ping_outcome(0, slow_transcript)
		assert.equals("s", sample)
		assert.equals(1400.123, ms)
		sample, ms = ping_window.ping_outcome(2, TIMEOUT_TRANSCRIPT)
		assert.equals("0", sample)
		assert.is_nil(ms)
		sample, ms = ping_window.ping_outcome(0, "reply without summary")
		assert.equals("1", sample)
		assert.is_nil(ms)
		for _, rc in ipairs({ 1, 64, 126, 127 }) do
			local result, problem = ping_window.ping_outcome(rc, SUCCESS_TRANSCRIPT)
			assert.is_nil(result)
			assert.is_not_nil(problem)
		end
		assert.is_nil(ping_window.ping_outcome(nil, ""))
	end)

	it("interprets curl success, portals, and TCP handshake latency", function()
		local body = "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>\n"
		local ok = ping_window.web_outcome(0, body .. "\n__PING_WINDOW__ 200 0.030000 0.150400", 1000)
		assert.same({ verdict = "ok", at = 1000, ms = 120, http_code = 200 }, ok)
		for _, case in ipairs({ { "Sign in", 200 }, { "Success", 302 }, { "Success", 503 } }) do
			local portal =
				ping_window.web_outcome(0, case[1] .. "\n__PING_WINDOW__ " .. case[2] .. " 0.001000 0.002000", 1000)
			assert.equals("portal", portal.verdict)
		end
		local spoof = "Success\n__PING_WINDOW__ 200 0.000000 0.001000\n__PING_WINDOW__ 302 0.001000 0.002000"
		assert.equals("portal", ping_window.web_outcome(0, spoof, 1000).verdict)
		assert.is_nil(ping_window.web_outcome(0, body, 1000))
		assert.is_nil(ping_window.web_outcome(0, body .. "\n__PING_WINDOW__ 200 1.000000 0.100000", 1000))
	end)

	it("separates curl network failures from tool failures", function()
		for rc, reason in pairs({
			[6] = "DNS lookup failed",
			[7] = "could not connect",
			[28] = "timed out",
			[35] = "curl exit 35",
		}) do
			local verdict = ping_window.web_outcome(rc, "\n__PING_WINDOW__ 000 0.000000 0.000000", 1000)
			assert.equals("fail", verdict.verdict)
			assert.equals(reason, verdict.reason)
			assert.equals(1000, verdict.at)
		end
		assert.same({ verdict = "fail", at = 1000, reason = "timed out" }, ping_window.web_outcome(28, "", 1000))
		for _, rc in ipairs({ 2, 126, 127 }) do
			local verdict, problem = ping_window.web_outcome(rc, "", 1000)
			assert.is_nil(verdict)
			assert.is_not_nil(problem)
		end
		assert.is_nil(ping_window.web_outcome(nil, "", 1000))
	end)
end)

-- This exact table is also consumed by the tmux and device-acceptance phases.
describe("shared connectivity fixtures", function()
	local count = 0
	for line in io.lines("tests/fixtures/ping_window_cases.tsv") do
		if line ~= "" and line:sub(1, 1) ~= "#" and line:sub(1, 5) ~= "name\t" then
			local fields = {}
			for value in (line .. "\t"):gmatch("(.-)\t") do
				table.insert(fields, value)
			end
			count = count + 1
			it(fields[1], function()
				assert.equals(8, #fields)
				local now, size = tonumber(fields[2]), tonumber(fields[3])
				local state = assert(ping_window.parse_state(fields[4]))
				assert.equals(fields[5], ping_window.assess(state, now, size).tier)
				local presentation = ping_window.presentation(state, now, { window_size = size })
				assert.equals(fields[5], presentation.tier)
				local value = ""
				for _, segment in ipairs(presentation.segments) do
					if segment.role == "count" or segment.role == "latency" or segment.role == "note" then
						value = segment.text:gsub(FIGURE_SPACE, "")
						if segment.role ~= "note" then
							assert.equals(5, codepoint_length(segment.text))
						end
					end
				end
				assert.equals(fields[6], value)
				assert.equals(presentation.title, concat_segments(presentation.segments))
			end)
		end
	end
	it("contains the full scenario matrix", function()
		assert.is_true(count >= 40)
	end)
end)

describe("v2 connectivity presentation", function()
	local function present(results, tokens, opts)
		return ping_window.presentation(
			ping_window.parse_state("1000 hammerspoon 1000 " .. results .. (tokens and " " .. tokens or "")),
			1000,
			opts
		)
	end
	local function row_text(presentation, kind)
		local row = find_row(presentation.menu, kind)
		return row and concat_segments(row.segments)
	end

	it("builds headers from the evidence without claiming an ICMP cause", function()
		local cases = {
			{ "sss", "rtt=1300,1400,1500", "✓ Slow · round trips take 1.4 s" },
			{ "000", "web=ok,1000,120", "✓ Online · pings unanswered" },
			{ "001", "web=ok,1000,120", "✓ Online · pings unreliable" },
			{ "000", "check=1000", "✗ Ping failed · checking the web…" },
			{ "100", "web=fail,1000,-", "✗ Ping failed · web check failed" },
			{ "100", "web=portal,1000,120", "✗ Ping failed · sign-in required?" },
			{ "000", "web=fail,1000,-", "✗ Offline · web check failed too" },
			{ "000", "web=portal,1000,120", "✗ Offline · sign-in required?" },
			{ "000", nil, "✗ Offline" },
		}
		for _, case in ipairs(cases) do
			assert.equals(case[3], row_text(present(case[1], case[2]), "header"))
		end
		assert.equals(
			"Internet: online · pings unanswered · 0 of 30 pings answered (0%)",
			present(string.rep("0", 30), "web=ok,1000,120").tooltip
		)
		assert.equals(
			"Internet: slow · round trips take 1.4 s · 3 of 3 pings answered (100%) · last reply 1.5 s",
			present("sss", "rtt=1300,1400,1500").tooltip
		)
	end)

	it("draws slow replies in the strip and counts them as answered", function()
		local presentation = present("1s0")
		local history = find_row(presentation.menu, "history")
		assert.equals("●◐○" .. string.rep("·", 27) .. "  now", concat_segments(history.segments))
		assert.equals("slow", history.segments[2].role)
		assert.equals("2 of 3 pings answered (67%) · last 6 s", row_text(presentation, "summary"))
	end)

	it("shows recent web evidence after last ping and expires the row at 301 seconds", function()
		local clock = os.date("%H:%M:%S", 1000)
		local presentation = present("000", "web=ok,1000,120")
		assert.equals("Web check OK · 120 ms round trip · " .. clock, row_text(presentation, "web"))
		assert.same(
			{ "header", "history", "summary", "last", "web", "separator", "info", "separator", "action" },
			menu_kinds(presentation.menu)
		)
		assert.equals("Web check OK · " .. clock, row_text(present("000", "web=ok,1000,-"), "web"))
		assert.equals(
			"Web check OK · 1.4 s round trip · " .. clock,
			row_text(present("000", "web=ok,1000,1400"), "web")
		)
		assert.equals(
			"Web check hit a sign-in page · " .. clock,
			row_text(present("000", "web=portal,1000,120"), "web")
		)
		assert.is_not_nil(row_text(present("000", "web=ok,700,120"), "web"))
		assert.is_nil(row_text(present("000", "web=ok,699,120"), "web"))
	end)

	it("uses failure detail only when its timestamp matches the verdict", function()
		local clock = os.date("%H:%M:%S", 1000)
		for _, reason in ipairs({ "timed out", "could not connect", "DNS lookup failed", "curl exit 35" }) do
			local matching = present("000", "web=fail,1000,-", { web_detail = { at = 1000, reason = reason } })
			assert.equals("Web check failed · " .. reason .. " · " .. clock, row_text(matching, "web"))
		end
		local stale_detail = present("000", "web=fail,1000,-", { web_detail = { at = 999, reason = "timed out" } })
		assert.equals("Web check failed · " .. clock, row_text(stale_detail, "web"))
		assert.equals("Web check failed · " .. clock, row_text(present("000", "web=fail,1000,-"), "web"))
	end)

	it("prefers persisted RTTs and never calls a missed ping a last reply", function()
		local opts = { rtt_ms = 18, rtt_sent_at = 1000 }
		local clock = os.date("%H:%M:%S", 1000)
		assert.equals("Last reply 1.4 s · " .. clock, row_text(present("s", "rtt=1400", opts), "last"))
		assert.equals("Last reply 18 ms · " .. clock, row_text(present("1", nil, opts), "last"))
		local missed = present("0", "rtt=1400", opts)
		assert.equals("Last ping failed · " .. clock, row_text(missed, "last"))
		assert.is_nil(missed.tooltip:find("last reply", 1, true))
	end)

	it("returns assessment evidence and identifies the latency source", function()
		local state = ping_window.parse_state("1000 hammerspoon 1000 sss rtt=1200,1400,1600 web=ok,999,2100 check=1000")
		local assessed = ping_window.assess(state, 1000, 30)
		assert.equals("slow", assessed.tier)
		assert.equals(1400, assessed.latency_ms)
		assert.equals("ping", assessed.latency_source)
		assert.is_true(assessed.web_ok)
		assert.is_false(assessed.web_bad)
		assert.is_true(assessed.checking)
		assert.same(state.web, assessed.web)
		state.results = "000"
		assessed = ping_window.assess(state, 1000, 30)
		assert.equals(2100, assessed.latency_ms)
		assert.equals("web", assessed.latency_source)
	end)

	it("classifies ping replies before rounding their stored RTT", function()
		local template = "round-trip min/avg/max/stddev = %s/%s/%s/0.000 ms\n"
		for _, case in ipairs({ { "499.999", "1" }, { "500.000", "s" } }) do
			local sample, ms = ping_window.ping_outcome(0, string.format(template, case[1], case[1], case[1]))
			assert.equals(case[2], sample)
			assert.equals(tonumber(case[1]), ms)
		end
	end)
end)
