local M = {}

M.OVERDUE_WARNING_AFTER_SECONDS = 10 * 60
M.MISSING_REMINDER_EVERY_SECONDS = 5 * 60
M.MISSING_REMINDER_FOR_SECONDS = 60
M.MAX_THEME_CODEPOINTS = 24
M.UNTITLED_THEME = "UNTITLED"
M.NO_POMODORO_TITLE = "NO POMODORO"
M.ICON = "🍅"

local EM_DASH = "—"
local ELLIPSIS = "…"
local ARROW = " → "
local SEPARATOR = " · "
local GAP = " "

M.ALERT_COLOR = "#E3413B"
M.MISSING_COLOR = "#30d158"
M.BADGE_TEXT_COLOR = "#FFFFFF"
M.MISSING_BADGE_TEXT_COLOR = "#062E14"

local function is_finite_number(value)
	return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function trim(text)
	local result = tostring(text or "")
	result = result:gsub("^%s+", "")
	result = result:gsub("%s+$", "")
	return result
end

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

local function truncate_to_codepoints(text, max_codepoints)
	local value = tostring(text or "")
	if codepoint_length(value) <= max_codepoints then
		return value
	end

	local count = 0
	local index = 1
	local total = #value
	local cut = total
	while index <= total do
		count = count + 1
		local byte = value:byte(index)
		local char_len = 1
		if byte >= 240 then
			char_len = 4
		elseif byte >= 224 then
			char_len = 3
		elseif byte >= 192 then
			char_len = 2
		end
		if count == max_codepoints then
			cut = index + char_len - 1
			break
		end
		index = index + char_len
	end
	return value:sub(1, cut)
end

local function format_seconds(seconds)
	local sign = ""
	if seconds < 0 then
		sign = "+"
		seconds = -seconds
	end

	seconds = math.floor(seconds)
	return string.format("%s%02d:%02d", sign, math.floor(seconds / 60), seconds % 60)
end

function M.normalize_theme(task_text)
	local label = tostring(task_text or "")
	label = label:gsub("%s+", " ")
	label = trim(label)

	if label:sub(1, #EM_DASH) == EM_DASH then
		label = trim(label:sub(#EM_DASH + 1))
	end

	if label == "" then
		return M.UNTITLED_THEME
	end
	return label
end

function M.shorten_theme(theme)
	local value = tostring(theme or "")
	if trim(value) == "" then
		return M.UNTITLED_THEME
	end
	if codepoint_length(value) <= M.MAX_THEME_CODEPOINTS then
		return value
	end

	local prefix = truncate_to_codepoints(value, M.MAX_THEME_CODEPOINTS - 1)
	prefix = prefix:gsub("%s+$", "")
	return prefix .. ELLIPSIS
end

function M.format_stop_time(end_hour, end_minute)
	return string.format("%02d:%02d", end_hour, end_minute)
end

function M.duration_minutes(start_hour, start_minute, end_hour, end_minute)
	if type(start_hour) ~= "number" or type(start_minute) ~= "number" then
		return nil
	end
	if type(end_hour) ~= "number" or type(end_minute) ~= "number" then
		return nil
	end
	local start_total = start_hour * 60 + start_minute
	local end_total = end_hour * 60 + end_minute
	local diff = (end_total - start_total) % 1440
	if diff == 0 then
		return nil
	end
	return diff
end

function M.format_duration(minutes)
	if not is_finite_number(minutes) then
		return nil
	end
	local floored = math.floor(minutes)
	if floored < 1 then
		return nil
	end
	return string.format("%dm", floored)
end

function M.missing_reminder_active(shown_seconds)
	if not is_finite_number(shown_seconds) or shown_seconds < 0 then
		return false
	end
	return shown_seconds % M.MISSING_REMINDER_EVERY_SECONDS < M.MISSING_REMINDER_FOR_SECONDS
end

function M.presentation(remaining_seconds, flash_on, context)
	if remaining_seconds == nil then
		local appearance = "missing"
		if type(context) == "table" and flash_on and M.missing_reminder_active(context.missingShownSeconds) then
			appearance = "missing_flash"
		end
		return {
			title = M.NO_POMODORO_TITLE,
			appearance = appearance,
			status = M.NO_POMODORO_TITLE,
			duration = nil,
			segments = {
				{ text = M.NO_POMODORO_TITLE, role = "missing" },
			},
		}
	end

	local full_theme = M.UNTITLED_THEME
	local stop = "00:00"
	if type(context) == "table" then
		local raw_theme = context.theme or context.fullTheme
		if raw_theme ~= nil and tostring(raw_theme) ~= "" then
			full_theme = M.normalize_theme(raw_theme)
		end
		if context.stop ~= nil and tostring(context.stop) ~= "" then
			stop = tostring(context.stop)
		elseif context.stopTime ~= nil and tostring(context.stopTime) ~= "" then
			stop = tostring(context.stopTime)
		elseif context.endHour ~= nil and context.endMinute ~= nil then
			stop = M.format_stop_time(context.endHour, context.endMinute)
		end
	end

	local display_theme = M.shorten_theme(full_theme)

	local duration = nil
	local duration_minutes = nil
	if type(context) == "table" then
		if type(context.duration) == "string" and context.duration ~= "" then
			duration = context.duration
		elseif context.durationMinutes ~= nil then
			duration = M.format_duration(context.durationMinutes)
		end
		if is_finite_number(context.durationMinutes) then
			duration_minutes = context.durationMinutes
		end
	end

	local status_text
	local appearance
	if remaining_seconds <= -M.OVERDUE_WARNING_AFTER_SECONDS then
		status_text = "OVERDUE"
		appearance = flash_on and "overdue_warning_flash" or "overdue_warning"
	elseif remaining_seconds < 0 then
		status_text = format_seconds(remaining_seconds)
		appearance = "overdue"
	else
		status_text = format_seconds(remaining_seconds)
		appearance = "normal"
	end

	local segments = {
		{ text = display_theme, role = "theme" },
	}
	if duration ~= nil then
		table.insert(segments, { text = GAP, role = "gap" })
		table.insert(segments, { text = "(" .. duration .. ")", role = "duration" })
	end
	if remaining_seconds < 0 or duration == nil then
		table.insert(segments, { text = ARROW, role = "arrow" })
		table.insert(segments, { text = stop, role = "stop" })
	end
	table.insert(segments, { text = SEPARATOR, role = "separator" })
	table.insert(segments, { text = M.ICON, role = "icon" })
	table.insert(segments, { text = GAP, role = "gap" })
	table.insert(segments, { text = status_text, role = "status" })

	local parts = {}
	for _, segment in ipairs(segments) do
		table.insert(parts, segment.text)
	end

	return {
		title = table.concat(parts),
		appearance = appearance,
		status = status_text,
		theme = display_theme,
		fullTheme = full_theme,
		stop = stop,
		duration = duration,
		durationMinutes = duration_minutes,
		icon = M.ICON,
		segments = segments,
	}
end

return M
