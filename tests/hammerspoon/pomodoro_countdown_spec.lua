package.path = "./home/dot_hammerspoon/?.lua;" .. package.path

local countdown = require("pomodoro_countdown")

local CONTEXT = { theme = "DEEP WORK", stop = "10:15", durationMinutes = 50 }

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

local function segment_roles(segments)
	local roles = {}
	for _, segment in ipairs(segments) do
		table.insert(roles, segment.role)
	end
	return roles
end

describe("Hammerspoon Pomodoro countdown presentation", function()
	it("formats running countdowns with theme, duration, tomato, and status", function()
		assert_presentation(754, false, CONTEXT, "DEEP WORK (50m) · 🍅 12:34", "normal")
		assert_presentation(601, false, CONTEXT, "DEEP WORK (50m) · 🍅 10:01", "normal")
		assert_presentation(0, false, CONTEXT, "DEEP WORK (50m) · 🍅 00:00", "normal")
		assert_presentation(6000, false, CONTEXT, "DEEP WORK (50m) · 🍅 100:00", "normal")
	end)

	it("omits the stop time while running when the duration is known", function()
		for _, remaining in ipairs({ 754, 601, 0, 6000 }) do
			local presentation = countdown.presentation(remaining, false, CONTEXT)
			assert.is_nil(presentation.title:find("10:15", 1, true))
			assert.is_true(presentation.title:find("(50m)", 1, true) ~= nil)
		end
	end)

	it("formats recently overdue countdowns with duration and stop time", function()
		assert_presentation(-1, false, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 +00:01", "overdue")
		assert_presentation(-599, false, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 +09:59", "overdue")
	end)

	it("uses the short OVERDUE status at and beyond the cutoff", function()
		assert.equals(600, countdown.OVERDUE_WARNING_AFTER_SECONDS)
		assert.equals(5, countdown.OVERDUE_PULSE_LAST_SECOND)
		assert_presentation(-600, false, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 OVERDUE", "overdue_warning")
		assert_presentation(-900, false, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 OVERDUE", "overdue_warning")
		assert_presentation(-600, true, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 OVERDUE", "overdue_warning_flash")
		assert_presentation(-3600, true, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 OVERDUE", "overdue_warning_flash")
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

	it("ignores the flash phase outside the overdue warning, minute pulse, and missing reminder states", function()
		assert_presentation(601, true, CONTEXT, "DEEP WORK (50m) · 🍅 10:01", "normal")
		assert_presentation(0, true, CONTEXT, "DEEP WORK (50m) · 🍅 00:00", "normal")
		assert_presentation(-6, true, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 +00:06", "overdue")
		assert_presentation(-599, true, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 +09:59", "overdue")
		assert_presentation(nil, true, CONTEXT, "NO POMODORO", "missing")
	end)

	it("pulses the overdue count for the first seconds of each minute", function()
		local active = { -0.5, -1, -5, -5.5, -60, -65, -120, -125, -540, -545 }
		for _, remaining in ipairs(active) do
			assert.is_true(countdown.overdue_pulse_active(remaining), tostring(remaining) .. " should pulse")
		end
		local inactive = { -6, -30, -59, -66, -119, -126, -546, -599 }
		for _, remaining in ipairs(inactive) do
			assert.is_false(countdown.overdue_pulse_active(remaining), tostring(remaining) .. " should rest")
		end
		for _, remaining in ipairs({ 1, 0, -600, -601, -900, -3600 }) do
			assert.is_false(countdown.overdue_pulse_active(remaining), tostring(remaining) .. " should rest")
		end
		assert.is_false(countdown.overdue_pulse_active(nil))
		assert.is_false(countdown.overdue_pulse_active("-1"))
		assert.is_false(countdown.overdue_pulse_active(0 / 0))
		assert.is_false(countdown.overdue_pulse_active(math.huge))
		assert.is_false(countdown.overdue_pulse_active(-math.huge))

		local count = 0
		for remaining = -1, -599, -1 do
			if countdown.overdue_pulse_active(remaining) then
				count = count + 1
				assert.is_true(math.floor(-remaining) % 60 <= countdown.OVERDUE_PULSE_LAST_SECOND)
			end
		end
		assert.equals(59, count)
	end)

	it("flashes the overdue count only inside a pulse", function()
		for _, remaining in ipairs({ -1, -60, -62, -540 }) do
			local steady = countdown.presentation(remaining, false, CONTEXT)
			local flashing = countdown.presentation(remaining, true, CONTEXT)
			assert.equals("overdue", steady.appearance)
			assert.equals("overdue_flash", flashing.appearance)
			assert.equals(steady.title, flashing.title)
			assert.equals(steady.status, flashing.status)
			assert.are.same(steady.segments, flashing.segments)
		end
		local pulsed = countdown.presentation(-60, false, CONTEXT)
		assert.equals("DEEP WORK (50m) → 10:15 · 🍅 +01:00", pulsed.title)

		for _, remaining in ipairs({ -6, -30, -599 }) do
			assert_presentation(
				remaining,
				false,
				CONTEXT,
				countdown.presentation(remaining, false, CONTEXT).title,
				"overdue"
			)
			assert_presentation(
				remaining,
				true,
				CONTEXT,
				countdown.presentation(remaining, false, CONTEXT).title,
				"overdue"
			)
		end

		for _, remaining in ipairs({ 0, 1, 601 }) do
			assert_presentation(
				remaining,
				false,
				CONTEXT,
				countdown.presentation(remaining, false, CONTEXT).title,
				"normal"
			)
			assert_presentation(
				remaining,
				true,
				CONTEXT,
				countdown.presentation(remaining, false, CONTEXT).title,
				"normal"
			)
		end
		assert_presentation(-600, false, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 OVERDUE", "overdue_warning")
		assert_presentation(-600, true, CONTEXT, "DEEP WORK (50m) → 10:15 · 🍅 OVERDUE", "overdue_warning_flash")
	end)

	it("exports the missing reminder constants", function()
		assert.equals(60, countdown.MISSING_REMINDER_FOR_SECONDS)
		assert.equals(60, countdown.MISSING_REMINDER_WAIT_UNIT_SECONDS)
		assert.equals("φ", countdown.PHI)
		assert.is_nil(countdown.MISSING_REMINDER_EVERY_SECONDS)
		assert.is_nil(countdown.MISSING_REMINDER_FIRST_AFTER_SECONDS)
		assert.equals("#062E14", countdown.MISSING_BADGE_TEXT_COLOR)
	end)

	it("schedules Fibonacci rests between fixed one-minute steps", function()
		local rows = {
			{ wait = 1, start = 60, stop = 120 },
			{ wait = 1, start = 180, stop = 240 },
			{ wait = 2, start = 360, stop = 420 },
			{ wait = 3, start = 600, stop = 660 },
			{ wait = 5, start = 960, stop = 1020 },
			{ wait = 8, start = 1500, stop = 1560 },
			{ wait = 13, start = 2340, stop = 2400 },
			{ wait = 21, start = 3660, stop = 3720 },
			{ wait = 34, start = 5760, stop = 5820 },
			{ wait = 55, start = 9120, stop = 9180 },
			{ wait = 89, start = 14520, stop = 14580 },
			{ wait = 144, start = 23220, stop = 23280 },
		}
		for _, row in ipairs(rows) do
			local step = countdown.missing_reminder_step(row.start)
			assert.is_true(step.active, tostring(row.start) .. " should be active")
			assert.equals(row.wait, step.waitMinutes)
			assert.equals(row.start, step.startSeconds)
			assert.equals(row.stop, step.endSeconds)
			assert.is_true(countdown.missing_reminder_step(row.start + 59).active)
			assert.is_true(countdown.missing_reminder_step(row.start + 59.5).active)
			assert.is_false(countdown.missing_reminder_step(row.start - 1).active)
			assert.is_false(countdown.missing_reminder_step(row.start + 60).active)
		end
	end)

	it("returns the upcoming step while resting between flashes", function()
		local cases = {
			{ shown = 0, wait = 1 },
			{ shown = 120, wait = 1 },
			{ shown = 240, wait = 2 },
			{ shown = 420, wait = 3 },
			{ shown = 660, wait = 5 },
			{ shown = 1020, wait = 8 },
		}
		for _, case in ipairs(cases) do
			local step = countdown.missing_reminder_step(case.shown)
			assert.is_false(step.active, tostring(case.shown) .. " should be inactive")
			assert.equals(case.wait, step.waitMinutes)
		end
	end)

	it("activates the missing reminder only inside each Fibonacci flash step", function()
		for _, shown in ipairs({ 60, 119, 180, 239, 360, 419, 600, 659, 960, 1500, 2340, 3660 }) do
			assert.is_true(countdown.missing_reminder_active(shown), tostring(shown) .. " should be active")
		end
		for _, shown in ipairs({ 0, 59, 120, 179, 240, 299, 300, 359, 420, 599, 660, 959, 1020, 1499 }) do
			assert.is_false(countdown.missing_reminder_active(shown), tostring(shown) .. " should be inactive")
		end
		assert.is_false(countdown.missing_reminder_active(-1))
		assert.is_false(countdown.missing_reminder_active(nil))
		assert.is_false(countdown.missing_reminder_active("0"))
		assert.is_false(countdown.missing_reminder_active(0 / 0))
		assert.is_false(countdown.missing_reminder_active(math.huge))
		assert.is_false(countdown.missing_reminder_active(-math.huge))
	end)

	it("previews the next Fibonacci reminder step", function()
		local function assert_next(shown, expected_start, expected_wait)
			local step = countdown.next_missing_reminder(shown)
			assert.is_not_nil(step, tostring(shown) .. " should have a next step")
			assert.equals(expected_start, step.startSeconds)
			assert.equals(expected_wait, step.waitMinutes)
			assert.is_false(step.active)
		end

		assert_next(0, 60, 1)
		assert_next(60, 180, 1)
		assert_next(119, 180, 1)
		assert_next(240, 360, 2)
		assert_next(600, 960, 5)
		assert.is_nil(countdown.next_missing_reminder(-1))
		assert.is_nil(countdown.next_missing_reminder(nil))
		assert.is_nil(countdown.next_missing_reminder("0"))
		assert.is_nil(countdown.next_missing_reminder(0 / 0))
		assert.is_nil(countdown.next_missing_reminder(math.huge))
		assert.is_nil(countdown.next_missing_reminder(-math.huge))
	end)

	it("shows the Fibonacci rest through the whole flash step with the φ suffix", function()
		local cases = {
			{ shown = 60, waited = 1, title = "NO POMODORO φ 1m" },
			{ shown = 180, waited = 1, title = "NO POMODORO φ 1m" },
			{ shown = 360, waited = 2, title = "NO POMODORO φ 2m" },
			{ shown = 600, waited = 3, title = "NO POMODORO φ 3m" },
			{ shown = 960, waited = 5, title = "NO POMODORO φ 5m" },
			{ shown = 23220, waited = 144, title = "NO POMODORO φ 144m" },
		}
		for _, case in ipairs(cases) do
			for _, flash_on in ipairs({ false, true }) do
				local expected_appearance = flash_on and "missing_flash" or "missing"
				local presentation = assert_presentation(
					nil,
					flash_on,
					{ missingShownSeconds = case.shown },
					case.title,
					expected_appearance
				)
				assert.are.same({
					{ text = "NO POMODORO", role = "missing" },
					{ text = " φ ", role = "phi" },
					{ text = case.waited .. "m", role = "waited" },
				}, presentation.segments)
				assert.equals(concat_segments(presentation.segments), presentation.title)
				assert.equals(case.waited, presentation.waitedMinutes)
				assert_valid_utf8(presentation.title)
				assert.is_nil(presentation.icon)
				assert.is_nil(presentation.title:find("🍅", 1, true))
				assert.equals("NO POMODORO", presentation.status)
				assert.is_nil(presentation.duration)
			end
		end
	end)

	it("flashes the missing presentation only during a reminder window with flash_on", function()
		local function assert_missing(remaining, flash_on, context, appearance)
			local presentation = assert_presentation(remaining, flash_on, context, "NO POMODORO", appearance)
			assert.are.same({ { text = "NO POMODORO", role = "missing" } }, presentation.segments)
			assert.is_nil(presentation.waitedMinutes)
			assert.is_nil(presentation.icon)
			assert.is_nil(presentation.title:find("🍅", 1, true))
			assert.equals("NO POMODORO", presentation.status)
			assert.is_nil(presentation.duration)
			return presentation
		end

		assert_missing(nil, true, { missingShownSeconds = 0 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 59 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 120 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 179 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 240 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 300 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 359 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 420 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 599 }, "missing")
		assert_missing(nil, true, { missingShownSeconds = 660 }, "missing")
		assert_missing(nil, true, nil, "missing")
		assert_missing(nil, true, CONTEXT, "missing")

		local session_context = {
			theme = "DEEP WORK",
			stop = "10:15",
			durationMinutes = 50,
			missingShownSeconds = 0,
		}
		assert_presentation(754, true, session_context, "DEEP WORK (50m) · 🍅 12:34", "normal")
		assert_presentation(
			-600,
			true,
			session_context,
			"DEEP WORK (50m) → 10:15 · 🍅 OVERDUE",
			"overdue_warning_flash"
		)
	end)

	it("uses the missing presentation only without a live countdown", function()
		local absent = assert_presentation(nil, false, nil, "NO POMODORO", "missing")
		local stale = assert_presentation(nil, false, CONTEXT, "NO POMODORO", "missing")
		for _, presentation in ipairs({ absent, stale }) do
			assert.are.same({ { text = "NO POMODORO", role = "missing" } }, presentation.segments)
			assert.equals(concat_segments(presentation.segments), presentation.title)
			assert.is_nil(presentation.icon)
			assert.is_nil(presentation.title:find("🍅", 1, true))
		end
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
				local expected = "DEEP WORK (50m)"
				if case.stop then
					expected = expected .. " → 10:15"
				end
				expected = expected .. " · 🍅 " .. case.status
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

	it("returns segment information in theme-first order with the tomato beside the countdown", function()
		local running = countdown.presentation(754, false, CONTEXT)
		assert.are.same({
			{ text = "DEEP WORK", role = "theme" },
			{ text = " ", role = "gap" },
			{ text = "(50m)", role = "duration" },
			{ text = " · ", role = "separator" },
			{ text = "🍅", role = "icon" },
			{ text = " ", role = "gap" },
			{ text = "12:34", role = "status" },
		}, running.segments)
		assert.are.same(
			{ "theme", "gap", "duration", "separator", "icon", "gap", "status" },
			segment_roles(running.segments)
		)

		local overdue = countdown.presentation(-1, false, CONTEXT)
		assert.are.same({
			{ text = "DEEP WORK", role = "theme" },
			{ text = " ", role = "gap" },
			{ text = "(50m)", role = "duration" },
			{ text = " → ", role = "arrow" },
			{ text = "10:15", role = "stop" },
			{ text = " · ", role = "separator" },
			{ text = "🍅", role = "icon" },
			{ text = " ", role = "gap" },
			{ text = "+00:01", role = "status" },
		}, overdue.segments)

		local missing = countdown.presentation(nil, false, CONTEXT)
		assert.are.same({
			{ text = "NO POMODORO", role = "missing" },
		}, missing.segments)
		assert.equals("NO POMODORO", missing.title)
		assert.is_nil(missing.icon)
	end)

	it("keeps exactly one ordinary space between the tomato and the countdown", function()
		local cases = { 754, 0, 6000, -1, -599, -600, -3600 }
		for _, remaining in ipairs(cases) do
			for _, flash in ipairs({ false, true }) do
				local presentation = countdown.presentation(remaining, flash, CONTEXT)
				assert.is_true(presentation.title:find("🍅 " .. presentation.status, 1, true) ~= nil)
				assert.is_nil(presentation.title:find("🍅  ", 1, true))
				assert.is_nil(presentation.title:find("🍅\194\160", 1, true))
				local roles = segment_roles(presentation.segments)
				assert.equals("separator", roles[#roles - 3])
				assert.equals("icon", roles[#roles - 2])
				assert.equals("gap", roles[#roles - 1])
				assert.equals("status", roles[#roles])
				assert.equals(" ", presentation.segments[#roles - 1].text)
			end
		end
	end)

	it("meets the alert contrast contract", function()
		local function hex_channels(hex)
			return tonumber(hex:sub(2, 3), 16), tonumber(hex:sub(4, 5), 16), tonumber(hex:sub(6, 7), 16)
		end

		local function srgb_to_linear(channel)
			local value = channel / 255
			if value <= 0.03928 then
				return value / 12.92
			end
			return ((value + 0.055) / 1.055) ^ 2.4
		end

		local function relative_luminance(hex)
			local red, green, blue = hex_channels(hex)
			return 0.2126 * srgb_to_linear(red) + 0.7152 * srgb_to_linear(green) + 0.0722 * srgb_to_linear(blue)
		end

		local function contrast_ratio(first, second)
			local first_luminance = relative_luminance(first)
			local second_luminance = relative_luminance(second)
			if first_luminance < second_luminance then
				first_luminance, second_luminance = second_luminance, first_luminance
			end
			return (first_luminance + 0.05) / (second_luminance + 0.05)
		end

		assert.equals(21, math.floor(contrast_ratio("#FFFFFF", "#000000") * 100 + 0.5) / 100)
		assert.equals(1, contrast_ratio("#E3413B", "#E3413B"))

		local light_reference = "#E6E6E6"
		local dark_reference = "#2E2E2E"
		assert.is_true(
			contrast_ratio(countdown.ALERT_COLOR, light_reference) >= 3.0,
			countdown.ALERT_COLOR .. " below 3:1 on the light bar"
		)
		assert.is_true(
			contrast_ratio(countdown.ALERT_COLOR, dark_reference) >= 3.0,
			countdown.ALERT_COLOR .. " below 3:1 on the dark bar"
		)

		assert.is_true(contrast_ratio(countdown.BADGE_TEXT_COLOR, countdown.ALERT_COLOR) >= 3.0)

		assert.equals("#30d158", countdown.MISSING_COLOR)
		assert.equals("#062E14", countdown.MISSING_BADGE_TEXT_COLOR)
		assert.is_true(contrast_ratio(countdown.MISSING_BADGE_TEXT_COLOR, countdown.MISSING_COLOR) >= 7.0)
		assert.is_true(contrast_ratio("#FFFFFF", countdown.MISSING_COLOR) < 3.0)

		assert.is_true(contrast_ratio("#65C3ED", light_reference) < 3.0)
		assert.is_true(contrast_ratio("#006381", dark_reference) < 3.0)
	end)

	it("leaves every presentation without a bucket", function()
		local running =
			countdown.presentation(3000, false, { theme = "DEEP WORK", stop = "10:15", durationMinutes = 50 })
		assert.is_nil(running.bucket)
		assert.equals(50, running.durationMinutes)
		assert.equals("DEEP WORK (50m) · 🍅 50:00", running.title)

		local zero = countdown.presentation(0, false, CONTEXT)
		assert.is_nil(zero.bucket)

		local overdue = countdown.presentation(-1, false, CONTEXT)
		assert.is_nil(overdue.bucket)

		local warning = countdown.presentation(-600, false, CONTEXT)
		assert.is_nil(warning.bucket)

		local warning_flash = countdown.presentation(-600, true, CONTEXT)
		assert.is_nil(warning_flash.bucket)

		local string_only =
			countdown.presentation(754, false, { theme = "DEEP WORK", stop = "10:15", duration = "50m" })
		assert.equals("DEEP WORK (50m) · 🍅 12:34", string_only.title)
		assert.equals("50m", string_only.duration)
		assert.is_nil(string_only.bucket)
		assert.is_nil(string_only.durationMinutes)

		local unknown = countdown.presentation(754, false, { theme = "DEEP WORK", stop = "10:15" })
		assert.is_nil(unknown.bucket)

		local missing = countdown.presentation(nil, false, CONTEXT)
		assert.is_nil(missing.bucket)
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
		assert.is_nil(countdown.format_duration(0 / 0))
		assert.is_nil(countdown.format_duration(math.huge))
		assert.is_nil(countdown.format_duration(-math.huge))
	end)

	it("resolves the duration from durationMinutes context", function()
		local presentation =
			countdown.presentation(754, false, { theme = "DEEP WORK", stop = "10:15", durationMinutes = 90 })
		assert.equals("DEEP WORK (90m) · 🍅 12:34", presentation.title)
		assert.equals("90m", presentation.duration)
	end)

	it("falls back to the stop time when the duration is unknown", function()
		local running = countdown.presentation(754, false, { theme = "DEEP WORK", stop = "10:15" })
		assert.equals("DEEP WORK → 10:15 · 🍅 12:34", running.title)
		assert.is_nil(running.duration)

		local overdue = countdown.presentation(-1, false, { theme = "DEEP WORK", stop = "10:15" })
		assert.equals("DEEP WORK → 10:15 · 🍅 +00:01", overdue.title)
		assert.is_nil(overdue.duration)
		local has_duration = false
		for _, segment in ipairs(overdue.segments) do
			if segment.role == "duration" then
				has_duration = true
			end
		end
		assert.is_false(has_duration)
	end)

	it("keeps the title invariant and the tomato beside the countdown in every state", function()
		local cases = { 754, 601, 0, 6000, -1, -599, -600, -900, -3600 }
		for _, remaining in ipairs(cases) do
			for _, flash in ipairs({ false, true }) do
				local presentation = countdown.presentation(remaining, flash, CONTEXT)
				assert.are.same({ text = "DEEP WORK", role = "theme" }, presentation.segments[1])
				assert.equals(concat_segments(presentation.segments), presentation.title)
				assert.is_true(presentation.title:find(presentation.status, 1, true) ~= nil)
				assert.is_true(presentation.title:find("(50m)", 1, true) ~= nil)
			end
		end
		for _, flash in ipairs({ false, true }) do
			local missing = countdown.presentation(nil, flash, CONTEXT)
			assert.are.same({ { text = "NO POMODORO", role = "missing" } }, missing.segments)
			assert.equals(concat_segments(missing.segments), missing.title)
			assert.equals("NO POMODORO", missing.title)
			assert.is_nil(missing.icon)
			assert.is_nil(missing.title:find("🍅", 1, true))
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
		assert.equals("Deep Work → 10:15 · 🍅 01:00", presentation.title)
	end)

	it("uses UNTITLED for empty or em-dash-only labels", function()
		assert.equals("UNTITLED", countdown.normalize_theme(""))
		assert.equals("UNTITLED", countdown.normalize_theme("   "))
		assert.equals("UNTITLED", countdown.normalize_theme("—"))
		assert.equals("UNTITLED", countdown.normalize_theme("—   "))
		assert.equals("UNTITLED", countdown.normalize_theme(nil))
		assert_presentation(60, false, { theme = "", stop = "10:15" }, "UNTITLED → 10:15 · 🍅 01:00", "normal")
		assert_presentation(60, false, { theme = "—", stop = "10:15" }, "UNTITLED → 10:15 · 🍅 01:00", "normal")
		assert_presentation(60, false, nil, "UNTITLED → 00:00 · 🍅 01:00", "normal")
	end)

	it("covers the UNTITLED duration grammar", function()
		assert_presentation(
			754,
			false,
			{ theme = "", stop = "10:15", duration = "50m" },
			"UNTITLED (50m) · 🍅 12:34",
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
		assert.equals(exact .. " → 10:15 · 🍅 01:00", presentation.title)
		presentation = countdown.presentation(60, false, { theme = over, stop = "10:15" })
		assert.equals(string.rep("B", 23) .. "… → 10:15 · 🍅 01:00", presentation.title)
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
		assert.equals("DEEP WORK → 09:05 · 🍅 01:00", presentation.title)
		assert.equals("09:05", presentation.stop)
	end)
end)
