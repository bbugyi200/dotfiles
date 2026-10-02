package.path = "./home/dot_hammerspoon/?.lua;" .. package.path

local countdown = require("pomodoro_countdown")

local CONTEXT = { theme = "DEEP WORK", stop = "10:15", duration = "50m" }

local function assert_presentation(remaining_seconds, flash_on, context, expected_title, expected_appearance)
	local presentation = countdown.presentation(remaining_seconds, flash_on, context)
	assert.equals(expected_title, presentation.title)
	assert.equals(expected_appearance, presentation.appearance)
	return presentation
end

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

local function assert_valid_utf8(text)
	local index = 1
	while index <= #text do
		local byte = text:byte(index)
		local char_len = 1
		if byte >= 240 then
			char_len = 4
		elseif byte >= 224 then
			char_len = 3
		elseif byte >= 192 then
			char_len = 2
		elseif byte >= 128 then
			error("stray continuation byte at index " .. index)
		end
		for offset = 1, char_len - 1 do
			local continuation = text:byte(index + offset)
			assert.is_true(
				continuation ~= nil and continuation >= 128 and continuation < 192,
				"truncated UTF-8 sequence at index " .. index
			)
		end
		index = index + char_len
	end
end

local function concat_segments(segments)
	local parts = {}
	for _, segment in ipairs(segments) do
		table.insert(parts, segment.text)
	end
	return table.concat(parts)
end

describe("Hammerspoon Pomodoro countdown presentation", function()
	it("formats running countdowns with tomato, theme, and duration", function()
		assert_presentation(754, false, CONTEXT, "🍅 DEEP WORK (50m) · 12:34", "normal")
		assert_presentation(601, false, CONTEXT, "🍅 DEEP WORK (50m) · 10:01", "normal")
		assert_presentation(0, false, CONTEXT, "🍅 DEEP WORK (50m) · 00:00", "normal")
		assert_presentation(6000, false, CONTEXT, "🍅 DEEP WORK (50m) · 100:00", "normal")
	end)

	it("omits the stop time while running when the duration is known", function()
		for _, remaining in ipairs({ 754, 601, 0, 6000 }) do
			local presentation = countdown.presentation(remaining, false, CONTEXT)
			assert.is_nil(presentation.title:find("10:15", 1, true))
			assert.is_true(presentation.title:find("(50m)", 1, true) ~= nil)
		end
	end)

	it("formats recently overdue countdowns with duration and stop time", function()
		assert_presentation(-1, false, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · +00:01", "overdue")
		assert_presentation(-599, false, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · +09:59", "overdue")
	end)

	it("uses the short OVERDUE status at and beyond the cutoff", function()
		assert.equals(600, countdown.OVERDUE_WARNING_AFTER_SECONDS)
		assert_presentation(-600, false, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · OVERDUE", "overdue_warning")
		assert_presentation(-900, false, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · OVERDUE", "overdue_warning")
		assert_presentation(-600, true, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · OVERDUE", "overdue_warning_flash")
		assert_presentation(-3600, true, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · OVERDUE", "overdue_warning_flash")
	end)

	it("never uses the retired OVERDUE POMODORO warning status", function()
		for _, remaining in ipairs({ -600, -601, -900, -3600 }) do
			for _, flash in ipairs({ false, true }) do
				local presentation = countdown.presentation(remaining, flash, CONTEXT)
				assert.equals("OVERDUE", presentation.status)
				assert.is_nil(presentation.title:find("POMODORO", 1, true))
			end
		end
	end)

	it("ignores the flash phase outside the overdue warning state", function()
		assert_presentation(601, true, CONTEXT, "🍅 DEEP WORK (50m) · 10:01", "normal")
		assert_presentation(0, true, CONTEXT, "🍅 DEEP WORK (50m) · 00:00", "normal")
		assert_presentation(-1, true, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · +00:01", "overdue")
		assert_presentation(-599, true, CONTEXT, "🍅 DEEP WORK (50m) → 10:15 · +09:59", "overdue")
		assert_presentation(nil, true, CONTEXT, "🍅 NO POMODORO", "missing")
	end)

	it("uses the missing presentation only without a live countdown", function()
		assert_presentation(nil, false, nil, "🍅 NO POMODORO", "missing")
		assert_presentation(nil, false, CONTEXT, "🍅 NO POMODORO", "missing")
	end)

	it("keeps theme, duration, stop time, and status in every current-session state", function()
		local cases = {
			{ remaining = 754, status = "12:34", stop = false },
			{ remaining = 0, status = "00:00", stop = false },
			{ remaining = -1, status = "+00:01", stop = true },
			{ remaining = -599, status = "+09:59", stop = true },
			{ remaining = -600, status = "OVERDUE", stop = true },
			{ remaining = -3600, status = "OVERDUE", stop = true },
		}
		for _, case in ipairs(cases) do
			for _, flash in ipairs({ false, true }) do
				local presentation = countdown.presentation(case.remaining, flash, CONTEXT)
				local expected = "🍅 DEEP WORK (50m)"
				if case.stop then
					expected = expected .. " → 10:15"
				end
				expected = expected .. " · " .. case.status
				assert.equals(expected, presentation.title)
				assert.equals(case.status, presentation.status)
				assert.equals("DEEP WORK", presentation.theme)
				assert.equals("DEEP WORK", presentation.fullTheme)
				assert.equals("10:15", presentation.stop)
				assert.equals("50m", presentation.duration)
				assert.equals("🍅", presentation.icon)
			end
		end
	end)

	it("returns segment information for independent styling", function()
		local running = countdown.presentation(754, false, CONTEXT)
		assert.are.same({
			{ text = "🍅", role = "icon" },
			{ text = " ", role = "gap" },
			{ text = "DEEP WORK", role = "theme" },
			{ text = " ", role = "gap" },
			{ text = "(50m)", role = "duration" },
			{ text = " · ", role = "separator" },
			{ text = "12:34", role = "status" },
		}, running.segments)

		local overdue = countdown.presentation(-1, false, CONTEXT)
		assert.are.same({
			{ text = "🍅", role = "icon" },
			{ text = " ", role = "gap" },
			{ text = "DEEP WORK", role = "theme" },
			{ text = " ", role = "gap" },
			{ text = "(50m)", role = "duration" },
			{ text = " → ", role = "arrow" },
			{ text = "10:15", role = "stop" },
			{ text = " · ", role = "separator" },
			{ text = "+00:01", role = "status" },
		}, overdue.segments)

		local missing = countdown.presentation(nil, false, CONTEXT)
		assert.are.same({
			{ text = "🍅", role = "icon" },
			{ text = " ", role = "gap" },
			{ text = "NO POMODORO", role = "missing" },
		}, missing.segments)
	end)

	it("derives durations from HHMM ranges with midnight wrap", function()
		assert.equals(25, countdown.duration_minutes(9, 50, 10, 15))
		assert.equals(50, countdown.duration_minutes(9, 25, 10, 15))
		assert.equals(50, countdown.duration_minutes(23, 30, 0, 20))
		assert.equals(1439, countdown.duration_minutes(0, 0, 23, 59))
		assert.is_nil(countdown.duration_minutes(10, 15, 10, 15))
		assert.is_nil(countdown.duration_minutes(nil, 15, 10, 15))
		assert.is_nil(countdown.duration_minutes(9, nil, 10, 15))
		assert.is_nil(countdown.duration_minutes(9, 50, nil, 15))
		assert.is_nil(countdown.duration_minutes(9, 50, 10, nil))
		assert.is_nil(countdown.duration_minutes("09", 50, 10, 15))
	end)

	it("formats durations as whole minutes without hour conversion", function()
		assert.equals("5m", countdown.format_duration(5))
		assert.equals("50m", countdown.format_duration(50))
		assert.equals("90m", countdown.format_duration(90))
		assert.equals("120m", countdown.format_duration(120))
		assert.is_nil(countdown.format_duration(0))
		assert.is_nil(countdown.format_duration(-5))
		assert.is_nil(countdown.format_duration(nil))
		assert.is_nil(countdown.format_duration("50"))
	end)

	it("resolves the duration from durationMinutes context", function()
		local presentation =
			countdown.presentation(754, false, { theme = "DEEP WORK", stop = "10:15", durationMinutes = 90 })
		assert.equals("🍅 DEEP WORK (90m) · 12:34", presentation.title)
		assert.equals("90m", presentation.duration)
	end)

	it("falls back to the stop time when the duration is unknown", function()
		local running = countdown.presentation(754, false, { theme = "DEEP WORK", stop = "10:15" })
		assert.equals("🍅 DEEP WORK → 10:15 · 12:34", running.title)
		assert.is_nil(running.duration)

		local overdue = countdown.presentation(-1, false, { theme = "DEEP WORK", stop = "10:15" })
		assert.equals("🍅 DEEP WORK → 10:15 · +00:01", overdue.title)
		assert.is_nil(overdue.duration)
		local has_duration = false
		for _, segment in ipairs(overdue.segments) do
			if segment.role == "duration" then
				has_duration = true
			end
		end
		assert.is_false(has_duration)
	end)

	it("keeps the tomato anchor and title invariant in every state", function()
		local cases = { 754, 601, 0, 6000, -1, -599, -600, -900, -3600 }
		for _, remaining in ipairs(cases) do
			for _, flash in ipairs({ false, true }) do
				local presentation = countdown.presentation(remaining, flash, CONTEXT)
				assert.are.same({ text = "🍅", role = "icon" }, presentation.segments[1])
				assert.equals(concat_segments(presentation.segments), presentation.title)
				assert.is_true(presentation.title:find(presentation.status, 1, true) ~= nil)
				assert.is_true(presentation.title:find("(50m)", 1, true) ~= nil)
			end
		end
		for _, flash in ipairs({ false, true }) do
			local missing = countdown.presentation(nil, flash, CONTEXT)
			assert.are.same({ text = "🍅", role = "icon" }, missing.segments[1])
			assert.equals(concat_segments(missing.segments), missing.title)
		end
	end)

	it("normalizes canonical names conservatively", function()
		assert.equals("DEEP WORK", countdown.normalize_theme("— DEEP WORK"))
		assert.equals("DEEP WORK", countdown.normalize_theme("—   DEEP   WORK  "))
		assert.equals("DEEP WORK", countdown.normalize_theme("  — DEEP WORK"))
		assert.equals("A — B", countdown.normalize_theme("— A — B"))
		assert.equals("— FOO", countdown.normalize_theme("— — FOO"))
		assert.equals("Deep Work", countdown.normalize_theme("— Deep Work"))
	end)

	it("preserves legacy labels, combined names, and internal dashes", function()
		assert.equals("DEEP WORK", countdown.normalize_theme("DEEP WORK"))
		assert.equals("BOB + SASE", countdown.normalize_theme("BOB + SASE"))
		assert.equals("BOB + SASE", countdown.normalize_theme("— BOB + SASE"))
		assert.equals("MEETING — PART 2", countdown.normalize_theme("MEETING — PART 2"))
		assert.equals("A — B — C", countdown.normalize_theme("A — B — C"))
	end)

	it("collapses whitespace and preserves authored case", function()
		assert.equals("DEEP WORK", countdown.normalize_theme("  DEEP   WORK  "))
		assert.equals("Deep Work", countdown.normalize_theme("Deep Work"))
		local presentation = countdown.presentation(60, false, { theme = "  Deep   Work  ", stop = "10:15" })
		assert.equals("🍅 Deep Work → 10:15 · 01:00", presentation.title)
	end)

	it("uses UNTITLED for empty or em-dash-only labels", function()
		assert.equals("UNTITLED", countdown.normalize_theme(""))
		assert.equals("UNTITLED", countdown.normalize_theme("   "))
		assert.equals("UNTITLED", countdown.normalize_theme("—"))
		assert.equals("UNTITLED", countdown.normalize_theme("—   "))
		assert.equals("UNTITLED", countdown.normalize_theme(nil))
		assert_presentation(60, false, { theme = "", stop = "10:15" }, "🍅 UNTITLED → 10:15 · 01:00", "normal")
		assert_presentation(60, false, { theme = "—", stop = "10:15" }, "🍅 UNTITLED → 10:15 · 01:00", "normal")
		assert_presentation(60, false, nil, "🍅 UNTITLED → 00:00 · 01:00", "normal")
	end)

	it("covers the UNTITLED duration grammar", function()
		assert_presentation(
			754,
			false,
			{ theme = "", stop = "10:15", duration = "50m" },
			"🍅 UNTITLED (50m) · 12:34",
			"normal"
		)
	end)

	it("keeps short themes complete and bounds long themes to 24 code points", function()
		assert.equals(24, countdown.MAX_THEME_CODEPOINTS)
		local exact = string.rep("A", 24)
		assert.equals(exact, countdown.shorten_theme(exact))
		local over = string.rep("B", 25)
		local shortened = countdown.shorten_theme(over)
		assert.equals(string.rep("B", 23) .. "…", shortened)
		assert.equals(24, codepoint_length(shortened))
		assert_valid_utf8(shortened)

		local presentation = countdown.presentation(60, false, { theme = exact, stop = "10:15" })
		assert.equals("🍅 " .. exact .. " → 10:15 · 01:00", presentation.title)
		presentation = countdown.presentation(60, false, { theme = over, stop = "10:15" })
		assert.equals("🍅 " .. string.rep("B", 23) .. "… → 10:15 · 01:00", presentation.title)
	end)

	it("trims trailing whitespace before appending the ellipsis", function()
		local theme = string.rep("A", 22) .. " " .. string.rep("B", 10)
		local shortened = countdown.shorten_theme(theme)
		assert.equals(string.rep("A", 22) .. "…", shortened)
		assert.is_nil(shortened:find(" …", 1, true))
	end)

	it("truncates multibyte names on code-point boundaries", function()
		local exact = string.rep("あ", 24)
		assert.equals(exact, countdown.shorten_theme(exact))
		local over = string.rep("あ", 25)
		local shortened = countdown.shorten_theme(over)
		assert_valid_utf8(shortened)
		assert.equals(24, codepoint_length(shortened))

		local mixed = string.rep("A", 23) .. "🎯extra"
		local mixed_shortened = countdown.shorten_theme(mixed)
		assert.equals(string.rep("A", 23) .. "…", mixed_shortened)
		assert_valid_utf8(mixed_shortened)

		local emoji_boundary = string.rep("A", 22) .. "🎯" .. string.rep("B", 10)
		local emoji_shortened = countdown.shorten_theme(emoji_boundary)
		assert_valid_utf8(emoji_shortened)
		assert.equals(24, codepoint_length(emoji_shortened))

		local presentation = countdown.presentation(60, false, { theme = over, stop = "10:15" })
		assert_valid_utf8(presentation.title)
		assert.is_true(presentation.title:find("10:15", 1, true) ~= nil)
	end)

	it("never truncates the duration, stop time, or status", function()
		local long_theme = string.rep("C", 100)
		for _, remaining in ipairs({ 754, 0, -1, -599, -600 }) do
			local presentation =
				countdown.presentation(remaining, false, { theme = long_theme, stop = "23:59", duration = "50m" })
			assert_valid_utf8(presentation.title)
			assert.is_true(presentation.title:find("(50m)", 1, true) ~= nil)
			assert.is_true(presentation.title:find(presentation.status, 1, true) ~= nil)
			if remaining < 0 then
				assert.is_true(presentation.title:find("23:59", 1, true) ~= nil)
			end
		end
	end)

	it("formats endpoints as zero-padded 24-hour HH:MM", function()
		assert.equals("00:00", countdown.format_stop_time(0, 0))
		assert.equals("12:00", countdown.format_stop_time(12, 0))
		assert.equals("23:59", countdown.format_stop_time(23, 59))
		assert.equals("09:05", countdown.format_stop_time(9, 5))
		assert.equals("10:15", countdown.format_stop_time(10, 15))
	end)

	it("derives the stop time from endHour and endMinute context", function()
		local presentation = countdown.presentation(60, false, { theme = "DEEP WORK", endHour = 9, endMinute = 5 })
		assert.equals("🍅 DEEP WORK → 09:05 · 01:00", presentation.title)
		assert.equals("09:05", presentation.stop)
	end)
end)
