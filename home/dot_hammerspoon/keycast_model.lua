-- Pure token, trail, privacy, and layout model for the recording keycast.
-- Input events are adapter-neutral tables: { key, modifiers, characters, repeat }.
local M = {}

M.DEFAULT_MODE = "all"
M.MODES = { all = true, chords = true, off = true }
M.ENTRY_TTL = 2
M.COALESCE_WINDOW = 0.45
M.MIN_REGION_WIDTH = 320
M.MIN_REGION_HEIGHT = 120
M.REGION_RIGHT_INSET = 16
M.REGION_BOTTOM_INSET = 76
M.FONT_SIZE_RATIO = 0.028
M.MIN_FONT_SIZE = 16
M.MAX_FONT_SIZE = 28
M.DEFAULT_CONTENT_WIDTH = 480

M.RECORDER_CHORDS = {
	{ key = "v", modifiers = { ctrl = true, alt = true, shift = true } },
	{ key = "s", modifiers = { ctrl = true, alt = true, shift = true } },
}

M.DENY_LIST = {
	["1password"] = true,
	["keychainaccess"] = true,
	["passwords"] = true,
	["bitwarden"] = true,
	comagilebitsonepassword = true,
	comagilebitsonepassword7 = true,
	comapplekeychainaccess = true,
	comapplepasswords = true,
	combitwardendesktop = true,
}

local MODIFIER_ALIASES = {
	ctrl = "ctrl",
	control = "ctrl",
	ctl = "ctrl",
	alt = "alt",
	option = "alt",
	opt = "alt",
	shift = "shift",
	cmd = "cmd",
	command = "cmd",
	meta = "cmd",
	super = "cmd",
	fn = "fn",
	["function"] = "fn",
}
local MODIFIER_ORDER = {
	{ name = "ctrl", label = "⌃" },
	{ name = "alt", label = "⌥" },
	{ name = "shift", label = "⇧" },
	{ name = "cmd", label = "⌘" },
}
local MODIFIER_KEYS = {
	ctrl = true,
	control = true,
	ctl = true,
	alt = true,
	option = true,
	opt = true,
	shift = true,
	cmd = true,
	command = true,
	meta = true,
	super = true,
	fn = true,
	["function"] = true,
}
local KEY_ALIASES = {
	esc = "escape",
	["return"] = "return",
	enter = "return",
	["↩"] = "return",
	["↩︎"] = "return",
	backspace = "delete",
	back = "delete",
	["⌫"] = "delete",
	forwarddelete = "forwarddelete",
	["⌦"] = "forwarddelete",
	[" "] = "space",
	spacebar = "space",
	["␣"] = "space",
	["⇥"] = "tab",
	["⎋"] = "escape",
	leftarrow = "left",
	rightarrow = "right",
	uparrow = "up",
	downarrow = "down",
}
local SPECIAL_LABELS = {
	escape = "⎋",
	["return"] = "↩︎",
	tab = "⇥",
	delete = "⌫",
	forwarddelete = "⌦",
	space = "␣",
	left = "←",
	right = "→",
	up = "↑",
	down = "↓",
	home = "↖",
	["end"] = "↘",
	pageup = "⇞",
	pagedown = "⇟",
	help = "Help",
	capslock = "⇪",
	grave = string.char(96),
	f1 = "F1",
	f2 = "F2",
	f3 = "F3",
	f4 = "F4",
	f5 = "F5",
	f6 = "F6",
	f7 = "F7",
	f8 = "F8",
	f9 = "F9",
	f10 = "F10",
	f11 = "F11",
	f12 = "F12",
}
local PRINTABLE_SPECIAL_KEYS = { grave = true }

-- macOS virtual key codes, kept here so the model does not need hs.keycodes.
local KEYCODES = {
	[0] = "a",
	[1] = "s",
	[2] = "d",
	[3] = "f",
	[4] = "h",
	[5] = "g",
	[6] = "z",
	[7] = "x",
	[8] = "c",
	[9] = "v",
	[11] = "b",
	[12] = "q",
	[13] = "w",
	[14] = "e",
	[15] = "r",
	[16] = "y",
	[17] = "t",
	[18] = "1",
	[19] = "2",
	[20] = "3",
	[21] = "4",
	[22] = "6",
	[23] = "5",
	[24] = "=",
	[25] = "9",
	[26] = "7",
	[27] = "-",
	[28] = "8",
	[29] = "0",
	[30] = "]",
	[31] = "o",
	[32] = "u",
	[33] = "[",
	[34] = "i",
	[35] = "p",
	[36] = "return",
	[37] = "l",
	[38] = "j",
	[39] = "'",
	[40] = "k",
	[41] = ";",
	[42] = "\\",
	[43] = ",",
	[44] = "/",
	[45] = "n",
	[46] = "m",
	[47] = ".",
	[48] = "tab",
	[49] = "space",
	[50] = "grave",
	[51] = "delete",
	[53] = "escape",
	[55] = "cmd",
	[56] = "shift",
	[57] = "capslock",
	[58] = "alt",
	[59] = "ctrl",
	[60] = "shift",
	[61] = "alt",
	[62] = "ctrl",
	[63] = "fn",
	[123] = "left",
	[124] = "right",
	[125] = "down",
	[126] = "up",
}

local function copy_table(value)
	local result = {}
	if type(value) == "table" then
		for key, item in pairs(value) do
			result[key] = item
		end
	end
	return result
end

local function is_number(value)
	return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function trim_lower(value)
	if type(value) ~= "string" then
		return nil
	end
	return value:match("^%s*(.-)%s*$"):lower()
end

local function normalize_key(key)
	if type(key) == "number" then
		key = KEYCODES[key]
	end
	local normalized = trim_lower(key)
	if normalized == nil then
		return nil
	end
	return KEY_ALIASES[normalized] or normalized
end

local function add_modifier(result, value)
	local normalized = trim_lower(value)
	local name = normalized and MODIFIER_ALIASES[normalized]
	if name then
		result[name] = true
	end
end

function M.normalizeModifiers(modifiers)
	local result = {}
	if type(modifiers) ~= "table" then
		return result
	end
	for key, value in pairs(modifiers) do
		if type(key) == "number" then
			add_modifier(result, value)
		elseif value == true then
			add_modifier(result, key)
		end
	end
	return result
end

local function has_chord_modifier(modifiers)
	return modifiers.ctrl == true or modifiers.alt == true or modifiers.cmd == true
end

local function is_modifier_key(key)
	return key ~= nil and MODIFIER_KEYS[key] == true
end

local function is_single_utf8_character(value)
	if type(value) ~= "string" or value == "" then
		return false
	end
	local first = value:byte(1)
	local length = #value
	local expected = first < 0x80 and 1 or first < 0xE0 and 2 or first < 0xF0 and 3 or 4
	if length ~= expected then
		return false
	end
	if expected == 1 then
		return first >= 0x20 and first ~= 0x7F
	end
	for index = 2, length do
		local byte = value:byte(index)
		if byte < 0x80 or byte > 0xBF then
			return false
		end
	end
	return true
end

local function format_label(key, modifiers, characters)
	local base = SPECIAL_LABELS[key]
	local printable = PRINTABLE_SPECIAL_KEYS[key] == true
	if base == nil and is_single_utf8_character(key) then
		base = key
		printable = key ~= " "
	end
	if base == nil or base == "" then
		return nil
	end

	if key == "space" then
		base = SPECIAL_LABELS.space
	end
	if printable and #base == 1 and base:match("%a") then
		if modifiers.shift or has_chord_modifier(modifiers) then
			base = base:upper()
		end
		-- A produced character preserves the active keyboard layout for plain typing.
		if not has_chord_modifier(modifiers) and is_single_utf8_character(characters) then
			base = characters
		end
	elseif printable and not has_chord_modifier(modifiers) and is_single_utf8_character(characters) then
		base = characters
	end

	local prefix = {}
	for _, item in ipairs(MODIFIER_ORDER) do
		if modifiers[item.name] then
			-- Shift is already visible in the case of a printable letter.
			if item.name ~= "shift" or not (printable and #base == 1 and base:match("%a")) then
				table.insert(prefix, item.label)
			end
		end
	end
	return table.concat(prefix) .. base, printable
end

-- Convert an adapter-neutral event into a display token. Bare modifier keys and
-- unknown key codes return nil. The token is a plain table suitable for testing.
function M.token(event)
	if type(event) ~= "table" then
		return nil
	end
	local key = normalize_key(event.key or event.keycode or event.key_code)
	if key == nil or is_modifier_key(key) then
		return nil
	end
	local modifiers = M.normalizeModifiers(event.modifiers or event.flags)
	local label, printable = format_label(key, modifiers, event.characters)
	if label == nil then
		return nil
	end
	return {
		key = key,
		label = label,
		printable = printable == true and not has_chord_modifier(modifiers),
		modifiers = modifiers,
		repeat_key = event["repeat"] == true or event.is_repeat == true,
	}
end

function M.keyToken(key, modifiers, characters)
	return M.token({ key = key, modifiers = modifiers, characters = characters })
end

function M.normalizeMode(mode)
	if M.MODES[mode] then
		return mode
	end
	return M.DEFAULT_MODE
end

function M.isRecorderChord(key, modifiers)
	key = normalize_key(key)
	modifiers = M.normalizeModifiers(modifiers)
	for _, chord in ipairs(M.RECORDER_CHORDS) do
		if
			key == chord.key
			and modifiers.ctrl == chord.modifiers.ctrl
			and modifiers.alt == chord.modifiers.alt
			and modifiers.shift == chord.modifiers.shift
			and modifiers.cmd ~= true
		then
			return true
		end
	end
	return false
end

local function compact_app_name(name)
	return (name:lower():gsub("[^%w]", ""))
end

function M.isDeniedApp(name)
	if type(name) ~= "string" or name == "" then
		return false
	end
	local normalized = compact_app_name(name)
	if M.DENY_LIST[normalized] then
		return true
	end
	return normalized:match("^1password") ~= nil
		or normalized:match("^comagilebitsonepassword") ~= nil
		or normalized:match("^comapplekeychainaccess$") ~= nil
		or normalized:match("^comapplepasswords$") ~= nil
		or normalized:match("^combitwarden") ~= nil
end

-- Return a token only when the selected mode permits it. Chords includes
-- command/control/option combinations; Shift by itself is ordinary typing.
function M.filter(mode, event, app_name)
	mode = M.normalizeMode(mode)
	if mode == "off" or type(event) ~= "table" then
		return nil
	end
	if event.type ~= nil and event.type ~= "keyDown" and event.type ~= "key_down" then
		return nil
	end
	if M.isDeniedApp(app_name or event.frontmost_app or event.app_name) then
		return nil
	end
	local token = M.token(event)
	if token == nil or M.isRecorderChord(token.key, token.modifiers) then
		return nil
	end
	if mode == "chords" and not has_chord_modifier(token.modifiers) then
		return nil
	end
	return token
end

local function entry_timestamp(entry)
	return entry.updated_at or entry.at
end

function M.expire(trail, now, ttl)
	local result = {}
	if type(trail) ~= "table" then
		return result
	end
	ttl = is_number(ttl) and math.max(0, ttl) or M.ENTRY_TTL
	now = is_number(now) and now or nil
	for _, entry in ipairs(trail) do
		if type(entry) == "table" then
			local timestamp = entry_timestamp(entry)
			if now == nil or not is_number(timestamp) or now - timestamp < ttl then
				table.insert(result, copy_table(entry))
			end
		end
	end
	return result
end

local function update_entry(entry, token, now)
	entry.updated_at = now
	entry.at = now
	entry.key = token.key
	entry.printable = token.printable
end

local function append_token(trail, token, now)
	local last = trail[#trail]
	if token.repeat_key and last and last.key == token.key then
		local repeated_from_text = false
		if last.kind == "token" and last.label == token.label then
			last.kind = "repeat"
			last.text = token.label
			last.count = 2
			last.label = token.label .. " ×2"
			update_entry(last, token, now)
			return trail
		end
		if last.kind == "text" and last.printable and last.text:sub(-#token.label) == token.label then
			repeated_from_text = true
			last.text = last.text:sub(1, #last.text - #token.label)
			last.label = last.text
			if last.text == "" then
				table.remove(trail)
				last = trail[#trail]
			end
		end
		if last and last.kind == "repeat" and last.key == token.key then
			last.count = last.count + 1
			last.label = last.text .. " ×" .. tostring(last.count)
			update_entry(last, token, now)
			return trail
		end
		local count = (repeated_from_text or (last and last.key == token.key)) and 2 or 1
		local entry = {
			kind = "repeat",
			key = token.key,
			text = token.label,
			label = count > 1 and token.label .. " ×" .. tostring(count) or token.label,
			printable = token.printable,
			count = count,
			at = now,
			updated_at = now,
		}
		table.insert(trail, entry)
		return trail
	end

	if token.printable and last and last.kind == "text" and last.count == 1 then
		local timestamp = entry_timestamp(last)
		if is_number(timestamp) and now - timestamp <= M.COALESCE_WINDOW then
			last.text = last.text .. token.label
			last.label = last.text
			update_entry(last, token, now)
			return trail
		end
	end

	table.insert(trail, {
		kind = token.printable and "text" or "token",
		key = token.key,
		text = token.label,
		label = token.label,
		printable = token.printable,
		count = 1,
		at = now,
		updated_at = now,
	})
	return trail
end

-- Add one accepted event to an immutable trail and return a new trail.
function M.append(trail, token, now)
	now = is_number(now) and now or 0
	local result = M.expire(trail, now)
	if type(token) ~= "table" or type(token.label) ~= "string" or token.label == "" then
		return result
	end
	local normalized = copy_table(token)
	normalized.key = normalize_key(normalized.key) or normalized.key
	normalized.printable = normalized.printable == true
	normalized.repeat_key = normalized.repeat_key == true
	return append_token(result, normalized, now)
end

-- Apply mode/privacy filtering, expiry, coalescing, and repeat collapse in one step.
-- A denied app, secure input, or off mode clears the trail immediately.
function M.update(trail, event, now, mode, app_name)
	now = is_number(now) and now or 0
	mode = M.normalizeMode(mode)
	local app = app_name or (type(event) == "table" and (event.frontmost_app or event.app_name))
	if mode == "off" or M.isDeniedApp(app) or (type(event) == "table" and event.secure == true) then
		return {}, nil
	end
	local result = M.expire(trail, now)
	local token = M.filter(mode, event, app)
	if token == nil then
		return result, nil
	end
	return M.append(result, token, now), token
end

local function valid_region(region)
	return type(region) == "table"
		and is_number(region.x)
		and is_number(region.y)
		and is_number(region.w)
		and is_number(region.h)
		and region.w > 0
		and region.h > 0
end

local function clamp(value, lower, upper)
	return math.max(lower, math.min(upper, value))
end

-- Return a single-line frame wholly inside the captured region. A renderer can
-- supply content_width after measuring the current trail label.
function M.layout(region, content_width)
	if not valid_region(region) then
		return { visible = false, reason = "invalid region" }
	end
	if region.w < M.MIN_REGION_WIDTH or region.h < M.MIN_REGION_HEIGHT then
		return { visible = false, reason = "region too small" }
	end

	local font_size = clamp(region.h * M.FONT_SIZE_RATIO, M.MIN_FONT_SIZE, M.MAX_FONT_SIZE)
	local height = font_size + 12
	local max_width = region.w - 2 * M.REGION_RIGHT_INSET
	local width = is_number(content_width) and content_width or math.min(M.DEFAULT_CONTENT_WIDTH, max_width)
	width = clamp(width, 1, max_width)
	local frame = {
		x = region.x + region.w - M.REGION_RIGHT_INSET - width,
		y = region.y + region.h - M.REGION_BOTTOM_INSET - height,
		w = width,
		h = height,
	}
	return {
		visible = true,
		anchor = "bottom_right",
		font_size = font_size,
		frame = frame,
	}
end

return M
