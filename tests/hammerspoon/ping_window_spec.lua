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
		assert.same({ "-n", "-q", "-c", "1", "-t", "1", "8.8.8.8" }, ping_window.PING_ARGS)
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
		local invalid = {
			nil,
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
			{ successes = 2, total = 5, trailing_failures = 2, newest_ok = false },
			ping_window.summarize("01100")
		)
		assert.same(
			{ successes = 4, total = 5, trailing_failures = 0, newest_ok = true },
			ping_window.summarize("01111")
		)
		assert.same({ successes = 0, total = 0, trailing_failures = 0, newest_ok = false }, ping_window.summarize(""))
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
		local cases = {
			{ results = string.rep("1", 30), sampled = now, tier = "online", glyph = "✓", count = "30/30" },
			{
				results = "000" .. string.rep("1", 25) .. "01",
				sampled = now,
				tier = "lossy",
				glyph = "✓",
				count = "26/30",
			},
			{ results = string.rep("1", 29) .. "0", sampled = now, tier = "down", glyph = "✗", count = "29/30" },
			{ results = string.rep("1", 27) .. "000", sampled = now, tier = "offline", glyph = "✗", count = "27/30" },
			{ results = string.rep("1", 30), sampled = now - 7, tier = "stale", glyph = "◌", count = "30/30" },
		}
		for _, case in ipairs(cases) do
			local state = { heartbeat = now, producer = "hammerspoon", sampled = case.sampled, results = case.results }
			local presentation = ping_window.presentation(state, now, {})
			assert.equals(case.tier, presentation.tier)
			assert.equals(NBSP .. case.glyph .. " " .. case.count .. NBSP, presentation.title)
			assert.same({ "pad", "glyph", "gap", "count", "pad" }, segment_roles(presentation.segments))
			assert.equals(presentation.title, concat_segments(presentation.segments))
		end
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
		assert.equals(NBSP .. "✓" .. " " .. "20/20" .. NBSP, presentation.title)
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
			"Internet: 26 of 30 pings answered (87%) · last reply 18 ms",
			ping_window.presentation(state, now, { rtt_ms = 18.345, rtt_sent_at = now }).tooltip
		)
		assert.equals("Internet: 26 of 30 pings answered (87%)", ping_window.presentation(state, now, {}).tooltip)
		assert.equals(
			"Internet: 26 of 30 pings answered (87%)",
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
		assert.equals("Pinging 8.8.8.8 every 2 s · shared with tmux", concat_segments(info.segments))
		local action = find_row(menu, "action")
		assert.equals("Network Settings…", concat_segments(action.segments))
		assert.equals("network_settings", action.action)
	end)
end)
