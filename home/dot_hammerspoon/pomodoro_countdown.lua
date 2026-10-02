local M = {}

M.OVERDUE_WARNING_AFTER_SECONDS = 10 * 60
M.MAX_THEME_CODEPOINTS = 24
M.UNTITLED_THEME = "UNTITLED"
M.NO_POMODORO_TITLE = "NO POMODORO"

local EM_DASH = "—"
local ELLIPSIS = "…"
local ARROW = " → "
local SEPARATOR = " · "

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

function M.presentation(remaining_seconds, flash_on, context)
	if remaining_seconds == nil then
		return {
			title = M.NO_POMODORO_TITLE,
			appearance = "missing",
			status = M.NO_POMODORO_TITLE,
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

	return {
		title = display_theme .. ARROW .. stop .. SEPARATOR .. status_text,
		appearance = appearance,
		status = status_text,
		theme = display_theme,
		fullTheme = full_theme,
		stop = stop,
		segments = {
			{ text = display_theme, role = "theme" },
			{ text = ARROW, role = "arrow" },
			{ text = stop, role = "stop" },
			{ text = SEPARATOR, role = "separator" },
			{ text = status_text, role = "status" },
		},
	}
end

return M
