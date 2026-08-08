local M = {}

M.OVERDUE_WARNING_AFTER_SECONDS = 10 * 60

local function format_seconds(seconds)
	local sign = ""
	if seconds < 0 then
		sign = "+"
		seconds = -seconds
	end

	seconds = math.floor(seconds)
	return string.format("%s%d:%02d", sign, math.floor(seconds / 60), seconds % 60)
end

function M.presentation(remaining_seconds)
	if remaining_seconds == nil then
		return {
			title = "NO POMODORO",
			appearance = "missing",
		}
	end

	if remaining_seconds <= -M.OVERDUE_WARNING_AFTER_SECONDS then
		return {
			title = "OVERDUE POMODORO",
			appearance = "overdue_warning",
		}
	end

	return {
		title = format_seconds(remaining_seconds),
		appearance = remaining_seconds < 0 and "overdue" or "normal",
	}
end

return M
