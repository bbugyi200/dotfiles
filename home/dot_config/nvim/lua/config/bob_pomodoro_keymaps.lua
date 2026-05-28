local M = {}

local bob_root = "/home/bryan/bob"
local pomodoros_heading_pattern = "^##%s+Pomodoros%s*$"
local level_two_heading_pattern = "^##%s+"

local function uv()
	return vim.uv or vim.loop
end

local function normalize_path(path)
	if path == nil or path == "" then
		return nil
	end

	local expanded = vim.fn.fnamemodify(vim.fn.expand(path), ":p")
	return uv().fs_realpath(expanded) or expanded:gsub("/+$", "")
end

local function with_trailing_slash(path)
	if path:sub(-1) == "/" then
		return path
	end

	return path .. "/"
end

local function get_lines(bufnr)
	return vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
end

local function normalize_bufnr(bufnr)
	if bufnr == nil or bufnr == 0 then
		return vim.api.nvim_get_current_buf()
	end

	return bufnr
end

local function notify(message, level)
	vim.notify(message, level or vim.log.levels.INFO, { title = "Bob Pomodoro" })
end

local function modulo_day(minutes)
	return ((minutes % 1440) + 1440) % 1440
end

local function valid_time(hours, minutes)
	return hours ~= nil and minutes ~= nil and hours >= 0 and hours <= 23 and minutes >= 0 and minutes <= 59
end

local function minutes_from_parts(hours, minutes)
	hours = tonumber(hours)
	minutes = tonumber(minutes)

	if not valid_time(hours, minutes) then
		return nil
	end

	return hours * 60 + minutes
end

function M.is_bob_buffer(bufnr)
	bufnr = normalize_bufnr(bufnr)

	local buffer_path = normalize_path(vim.api.nvim_buf_get_name(bufnr))
	if buffer_path == nil then
		return false
	end

	local root = normalize_path(bob_root) or bob_root
	root = with_trailing_slash(root)

	return buffer_path:sub(1, #root) == root
end

function M.find_pomodoros_section(lines)
	local heading_lnum = nil

	for lnum, line in ipairs(lines) do
		if line:match(pomodoros_heading_pattern) then
			heading_lnum = lnum
			break
		end
	end

	if heading_lnum == nil then
		return nil
	end

	local end_lnum = #lines
	for lnum = heading_lnum + 1, #lines do
		if lines[lnum]:match(level_two_heading_pattern) then
			end_lnum = lnum - 1
			break
		end
	end

	return {
		heading_lnum = heading_lnum,
		start_lnum = heading_lnum + 1,
		end_lnum = end_lnum,
	}
end

function M.add_minutes(minutes, delta)
	return modulo_day(minutes + delta)
end

function M.format_time(minutes, style)
	minutes = modulo_day(minutes)

	local hours = math.floor(minutes / 60)
	local minute_part = minutes % 60

	if style == "colon" then
		return string.format("%02d:%02d", hours, minute_part)
	end

	return string.format("%02d%02d", hours, minute_part)
end

function M.parse_time_range(line)
	local start_pos, end_pos, start_hour, start_minute, end_hour, end_minute =
		line:find("%((%d%d):(%d%d)%s*%-%s*(%d%d):(%d%d)%)")

	if start_pos ~= nil then
		local start_minutes = minutes_from_parts(start_hour, start_minute)
		local end_minutes = minutes_from_parts(end_hour, end_minute)

		if start_minutes == nil or end_minutes == nil then
			return nil
		end

		return {
			start_pos = start_pos,
			end_pos = end_pos,
			start_minutes = start_minutes,
			end_minutes = end_minutes,
			style = "colon",
		}
	end

	local compact_start
	local compact_end
	start_pos, end_pos, compact_start, compact_end = line:find("%((%d%d%d%d)%s*%-%s*(%d%d%d%d)%)")

	if start_pos == nil then
		return nil
	end

	local compact_start_hour = compact_start:sub(1, 2)
	local compact_start_minute = compact_start:sub(3, 4)
	local compact_end_hour = compact_end:sub(1, 2)
	local compact_end_minute = compact_end:sub(3, 4)
	local start_minutes = minutes_from_parts(compact_start_hour, compact_start_minute)
	local end_minutes = minutes_from_parts(compact_end_hour, compact_end_minute)

	if start_minutes == nil or end_minutes == nil then
		return nil
	end

	return {
		start_pos = start_pos,
		end_pos = end_pos,
		start_minutes = start_minutes,
		end_minutes = end_minutes,
		style = "compact",
	}
end

function M.format_time_range(start_minutes, end_minutes, style)
	return "(" .. M.format_time(start_minutes, style) .. "-" .. M.format_time(end_minutes, style) .. ")"
end

function M.replace_time_range(line, range, start_minutes, end_minutes)
	local new_range = M.format_time_range(start_minutes, end_minutes, range.style)
	return line:sub(1, range.start_pos - 1) .. new_range .. line:sub(range.end_pos + 1)
end

function M.parse_ledger_line(line)
	local checkbox = line:match("^%s*[-*+]%s+%[([^%]])%]%s+")

	if checkbox == nil then
		return nil
	end

	return {
		checkbox = checkbox,
		completed = checkbox == "x" or checkbox == "X",
		unchecked = checkbox == " ",
		range = M.parse_time_range(line),
		placeholder = line:find("%(%s*%)") ~= nil,
	}
end

function M.find_active_item(lines)
	local section = M.find_pomodoros_section(lines)
	if section == nil then
		return nil, "No ## Pomodoros section found"
	end

	local latest_timed = nil
	local first_placeholder = nil

	for lnum = section.start_lnum, section.end_lnum do
		local line = lines[lnum]
		local entry = M.parse_ledger_line(line)

		if entry ~= nil and entry.unchecked then
			local item = {
				lnum = lnum,
				line = line,
				entry = entry,
			}

			if entry.range ~= nil then
				latest_timed = item
			elseif entry.placeholder and first_placeholder == nil then
				first_placeholder = item
			end
		end
	end

	if latest_timed ~= nil then
		return latest_timed
	end

	if first_placeholder ~= nil then
		return first_placeholder
	end

	return nil, "No active Pomodoro line found"
end

function M.adjust_p_metadata(line, delta)
	local start_pos, end_pos, spacing, value = line:find("%[%[p::(%s*)(%d+)%]%]")
	local new_value = math.max(0, (tonumber(value) or 0) + delta)

	if start_pos == nil then
		return line .. " [[p:: " .. new_value .. "]]", new_value
	end

	local metadata = "[[p::" .. spacing .. new_value .. "]]"
	return line:sub(1, start_pos - 1) .. metadata .. line:sub(end_pos + 1), new_value
end

local function current_line_target(bufnr, section, require_range)
	if vim.api.nvim_get_current_buf() ~= bufnr then
		return nil
	end

	local lnum = vim.api.nvim_win_get_cursor(0)[1]
	if lnum < section.start_lnum or lnum > section.end_lnum then
		return nil
	end

	local line = vim.api.nvim_buf_get_lines(bufnr, lnum - 1, lnum, false)[1]
	if line == nil then
		return nil
	end

	local entry = M.parse_ledger_line(line)
	if entry == nil then
		return nil
	end

	if require_range and entry.range == nil then
		return nil
	end

	return {
		lnum = lnum,
		line = line,
		entry = entry,
	}
end

function M.resolve_edit_target(bufnr, opts)
	bufnr = normalize_bufnr(bufnr)
	opts = opts or {}

	local lines = get_lines(bufnr)
	local section = M.find_pomodoros_section(lines)

	if section == nil then
		return nil, "No ## Pomodoros section found"
	end

	local target = current_line_target(bufnr, section, opts.require_range)
	if target ~= nil then
		return target
	end

	target = M.find_active_item(lines)
	if target == nil then
		return nil, "No active Pomodoro line found"
	end

	if opts.require_range and target.entry.range == nil then
		return nil, "No Pomodoro line with a time range found"
	end

	return target
end

function M.jump_to_current(bufnr)
	bufnr = normalize_bufnr(bufnr)

	local target, err = M.find_active_item(get_lines(bufnr))
	if target == nil then
		notify(err or "No active Pomodoro line found")
		return false
	end

	vim.api.nvim_win_set_cursor(0, { target.lnum, 0 })
	return true
end

function M.change_pomodoro_units(bufnr, units)
	bufnr = normalize_bufnr(bufnr)

	local target, err = M.resolve_edit_target(bufnr, { require_range = true })
	if target == nil then
		notify(err or "No Pomodoro line with a time range found")
		return false
	end

	local range = target.entry.range
	local new_line =
		M.replace_time_range(target.line, range, range.start_minutes, M.add_minutes(range.end_minutes, units * 5))
	new_line = M.adjust_p_metadata(new_line, units)

	vim.api.nvim_buf_set_lines(bufnr, target.lnum - 1, target.lnum, false, { new_line })
	return true
end

function M.offset_time_range(bufnr, minutes)
	bufnr = normalize_bufnr(bufnr)

	local target, err = M.resolve_edit_target(bufnr, { require_range = true })
	if target == nil then
		notify(err or "No Pomodoro line with a time range found")
		return false
	end

	local range = target.entry.range
	local new_line = M.replace_time_range(
		target.line,
		range,
		M.add_minutes(range.start_minutes, minutes),
		M.add_minutes(range.end_minutes, minutes)
	)

	vim.api.nvim_buf_set_lines(bufnr, target.lnum - 1, target.lnum, false, { new_line })
	return true
end

local function set_keymap(bufnr, lhs, callback, desc)
	vim.keymap.set("n", lhs, callback, {
		buffer = bufnr,
		nowait = true,
		desc = desc,
	})
end

function M.setup_buffer(bufnr)
	bufnr = normalize_bufnr(bufnr)

	if not M.is_bob_buffer(bufnr) then
		return false
	end

	if M.find_pomodoros_section(get_lines(bufnr)) == nil then
		return false
	end

	set_keymap(bufnr, "<localleader><localleader>", function()
		M.jump_to_current(bufnr)
	end, "Jump to active Bob Pomodoro")

	set_keymap(bufnr, "<localleader>p", function()
		M.change_pomodoro_units(bufnr, vim.v.count1)
	end, "Add Bob Pomodoro unit")

	set_keymap(bufnr, "<localleader>P", function()
		M.change_pomodoro_units(bufnr, -vim.v.count1)
	end, "Subtract Bob Pomodoro unit")

	set_keymap(bufnr, "<localleader>o", function()
		M.offset_time_range(bufnr, vim.v.count1 * 5)
	end, "Move Bob Pomodoro range later")

	set_keymap(bufnr, "<localleader>O", function()
		M.offset_time_range(bufnr, -vim.v.count1 * 5)
	end, "Move Bob Pomodoro range earlier")

	return true
end

return M
