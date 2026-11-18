-- Hammerspoon runtime for the recording keycast.
--
-- Requiring this module is safe outside Hammerspoon; hs APIs are used only after
-- show() starts a live overlay.
local Model = require("keycast_model")

local M = {}
local unpackArgs = table.unpack or _G.unpack

if type(BobKeycast) ~= "table" then
	BobKeycast = {}
end

local runtime = BobKeycast
runtime.trail = runtime.trail or {}

local function traceback(error_message)
	if debug and type(debug.traceback) == "function" then
		return debug.traceback(tostring(error_message), 2)
	end
	return tostring(error_message)
end

local function now_seconds()
	if hs.timer and type(hs.timer.secondsSinceEpoch) == "function" then
		return hs.timer.secondsSinceEpoch()
	end
	return os.time()
end

local function copy_region(region)
	return {
		x = region.x,
		y = region.y,
		w = region.w,
		h = region.h,
	}
end

local function same_region(left, right)
	return type(left) == "table"
		and type(right) == "table"
		and left.x == right.x
		and left.y == right.y
		and left.w == right.w
		and left.h == right.h
end

local function log_failure(error_message)
	if runtime.failure_logged then
		return
	end
	runtime.failure_logged = true
	if type(hs) == "table" and type(hs.printf) == "function" then
		pcall(hs.printf, "Bob keycast failed: %s", tostring(error_message))
	end
end

local function stop_object(object, method)
	if object then
		pcall(function()
			local operation = object[method]
			if type(operation) == "function" then
				operation(object)
			end
		end)
	end
end

local function release_visuals()
	stop_object(runtime.tap, "stop")
	stop_object(runtime.expiry_timer, "stop")
	stop_object(runtime.redraw_timer, "stop")
	stop_object(runtime.application_watcher, "stop")
	stop_object(runtime.canvas, "delete")
	runtime.tap = nil
	runtime.expiry_timer = nil
	runtime.redraw_timer = nil
	runtime.application_watcher = nil
	runtime.canvas = nil
	runtime.active = false
end

function M.hide()
	release_visuals()
	runtime.session_id = nil
	runtime.region = nil
	runtime.mode = nil
	runtime.secure = false
	runtime.denied = false
	runtime.indicator = false
	runtime.trail = {}
	runtime.key_names_by_code = nil
	return true
end

local function fail_session(session_id, error_message)
	if session_id ~= nil then
		runtime.failed_session_id = session_id
	end
	log_failure(error_message)
	M.hide()
	if session_id ~= nil then
		runtime.failed_session_id = session_id
	end
end

local function guarded_callback(name, callback)
	local ok, error_message = xpcall(callback, traceback)
	if not ok then
		fail_session(runtime.session_id, name .. ": " .. tostring(error_message))
	end
	return ok
end

local function get_application_value(application, key)
	if application == nil then
		return nil
	end
	local ok, value = pcall(function()
		local member = application[key]
		if type(member) == "function" then
			return member(application)
		end
		return member
	end)
	if ok and type(value) == "string" then
		return value
	end
	return nil
end

local function application_is_denied(application)
	return Model.isDeniedApp(get_application_value(application, "bundleID"))
		or Model.isDeniedApp(get_application_value(application, "name"))
end

local function frontmost_application()
	if hs.application and type(hs.application.frontmostApplication) == "function" then
		return hs.application.frontmostApplication()
	end
	return nil
end

local function update_indicator()
	local blocked = runtime.secure or runtime.denied
	if blocked then
		runtime.trail = {}
	end
	local changed = runtime.indicator ~= blocked
	runtime.indicator = blocked
	return changed
end

local function poll_secure_input()
	local secure = hs.eventtap.isSecureInputEnabled() == true
	local changed = runtime.secure ~= secure
	runtime.secure = secure
	return update_indicator() or changed
end

local function utf8_length(text)
	if utf8 and type(utf8.len) == "function" then
		local ok, length = pcall(utf8.len, text)
		if ok and type(length) == "number" then
			return length
		end
	end
	return #text
end

local function measure_label(text, font_size)
	return utf8_length(text) * font_size * 0.62 + 22
end

local function entry_alpha(entry, now)
	local updated = entry.updated_at or entry.at or now
	local age = math.max(0, now - updated)
	local ttl = Model.ENTRY_TTL or 2
	local fade = math.min(0.4, ttl)
	if age <= ttl - fade then
		return 1
	end
	return math.max(0, (ttl - age) / fade)
end

local function visible_pills(max_width, font_size, now)
	local trail = runtime.trail or {}
	local chosen = {}
	local width = 0
	local gap = 6
	for index = #trail, 1, -1 do
		local entry = trail[index]
		local label = type(entry.label) == "string" and entry.label or ""
		local pill_width = measure_label(label, font_size)
		local next_width = width + pill_width + (#chosen > 0 and gap or 0)
		if #chosen == 0 and pill_width > max_width then
			pill_width = max_width
			next_width = max_width
		end
		if next_width > max_width then
			break
		end
		table.insert(chosen, {
			text = label,
			width = pill_width,
			alpha = entry_alpha(entry, now),
		})
		width = next_width
	end
	return chosen, width, gap
end

local function canvas_elements(layout, pills, gap)
	local elements = {}
	local font_size = layout.font_size
	local y = math.max(0, (layout.frame.h - font_size) / 2)
	local x = layout.frame.w
	for _, pill in ipairs(pills) do
		x = x - pill.width
		table.insert(elements, {
			type = "rectangle",
			action = "fill",
			frame = { x = x, y = 0, w = pill.width, h = layout.frame.h },
			fillColor = { red = 0, green = 0, blue = 0, alpha = 0.72 * pill.alpha },
			roundedCorners = true,
			radius = layout.frame.h / 2,
		})
		table.insert(elements, {
			type = "text",
			action = "fill",
			frame = { x = x + 8, y = y, w = math.max(1, pill.width - 16), h = font_size },
			text = pill.text,
			textColor = { white = 1, alpha = pill.alpha },
			textFont = "Menlo",
			textSize = font_size,
			textAlignment = "center",
		})
		x = x - gap
	end
	return elements
end

local function redraw()
	local canvas = runtime.canvas
	if not canvas then
		return
	end

	local now = now_seconds()
	local max_width = runtime.region.w - 2 * (Model.REGION_RIGHT_INSET or 16)
	local provisional_font = math.max(
		Model.MIN_FONT_SIZE or 16,
		math.min(Model.MAX_FONT_SIZE or 28, runtime.region.h * (Model.FONT_SIZE_RATIO or 0.028))
	)
	local pills, content_width, gap
	if runtime.indicator then
		local indicator_width = math.min(max_width, measure_label("🔒 secure", provisional_font))
		pills = { { text = "🔒 secure", width = indicator_width, alpha = 0.72 } }
		content_width = indicator_width
		gap = 0
	else
		pills, content_width, gap = visible_pills(max_width, provisional_font, now)
	end

	if #pills == 0 then
		canvas:hide()
		return
	end

	local layout = Model.layout(runtime.region, content_width)
	if not layout.visible then
		canvas:hide()
		return
	end
	canvas:frame(layout.frame)
	local elements = canvas_elements(layout, pills, gap)
	canvas:replaceElements(unpackArgs(elements))
	canvas:show()
end

local function request_redraw()
	if runtime.redraw_timer then
		return
	end
	runtime.redraw_timer = hs.timer.delayed.new(0.016, function()
		guarded_callback("redraw timer", function()
			runtime.redraw_timer = nil
			redraw()
		end)
	end)
	runtime.redraw_timer:start()
end

local function update_frontmost_application()
	runtime.denied = application_is_denied(frontmost_application())
	return update_indicator()
end

local function start_application_watcher()
	runtime.application_watcher = hs.application.watcher.new(function()
		guarded_callback("application watcher", function()
			if update_frontmost_application() then
				request_redraw()
			end
		end)
	end)
	runtime.application_watcher:start()
end

local function start_expiry_timer()
	runtime.expiry_timer = hs.timer.new(0.25, function()
		guarded_callback("expiry timer", function()
			local old_count = #runtime.trail
			runtime.trail = Model.expire(runtime.trail, now_seconds())
			local privacy_changed = poll_secure_input()
			if privacy_changed or old_count ~= #runtime.trail or #runtime.trail > 0 then
				redraw()
			end
		end)
	end)
	runtime.expiry_timer:start()
end

local function key_names_by_code()
	local result = {}
	local map = hs.keycodes and hs.keycodes.map or {}
	for name, code in pairs(map) do
		if type(name) == "string" and type(code) == "number" and result[code] == nil then
			result[code] = name
		end
	end
	return result
end

local function event_key_code(event)
	if type(event.getKeyCode) == "function" then
		return event:getKeyCode()
	end
	return nil
end

local function event_flags(event)
	if type(event.getFlags) == "function" then
		return event:getFlags() or {}
	end
	return {}
end

local function event_characters(event)
	if type(event.getCharacters) == "function" then
		return event:getCharacters() or ""
	end
	return ""
end

local function event_is_repeat(event)
	local properties = hs.eventtap.event.properties
	local repeat_property = properties and properties.keyboardEventAutorepeat
	if repeat_property ~= nil and type(event.getProperty) == "function" then
		local value = event:getProperty(repeat_property)
		return value == 1 or value == true
	end
	return false
end

local function handle_key_event(event)
	local privacy_changed = poll_secure_input()
	if update_indicator() then
		privacy_changed = true
	end
	if runtime.indicator then
		if privacy_changed then
			request_redraw()
		end
		return
	end

	local key_code = event_key_code(event)
	local map = hs.keycodes and hs.keycodes.map or {}
	local key = map[key_code]
	if type(key) ~= "string" then
		key = runtime.key_names_by_code[key_code] or key_code
	end
	local flags = event_flags(event)
	local info = {
		type = "keyDown",
		key = key,
		characters = event_characters(event),
		modifiers = flags,
		["repeat"] = event_is_repeat(event),
	}
	local old_count = #runtime.trail
	runtime.trail = Model.update(runtime.trail, info, now_seconds(), runtime.mode)
	if old_count ~= #runtime.trail or #runtime.trail > 0 then
		request_redraw()
	end
end

local function start_event_tap()
	local key_down = hs.eventtap.event.types.keyDown
	runtime.tap = hs.eventtap.new({ key_down }, function(event)
		guarded_callback("event tap", function()
			handle_key_event(event)
		end)
		return false
	end)
	runtime.tap:start()
end

local function create_canvas()
	local layout = Model.layout(runtime.region)
	runtime.canvas = hs.canvas.new(layout.frame)
	runtime.canvas:level("screenSaver")
	runtime.canvas:behaviorAsLabels({ "canJoinAllSpaces", "fullScreenAuxiliary" })
	runtime.canvas:clickActivating(false)
	runtime.canvas:hide()
end

local function start_visuals()
	local application_changed = update_frontmost_application()
	poll_secure_input()
	create_canvas()
	start_application_watcher()
	start_expiry_timer()
	runtime.key_names_by_code = key_names_by_code()
	start_event_tap()
	runtime.active = true
	if application_changed or runtime.indicator then
		redraw()
	end
end

local function validate_show_args(item)
	assert(type(item) == "table", "show expects an options table")
	assert(type(item.session_id) == "string" and item.session_id ~= "", "show requires a session id")
	assert(type(item.region) == "table", "show requires a region")
	assert(
		type(item.region.x) == "number"
			and type(item.region.y) == "number"
			and type(item.region.w) == "number"
			and type(item.region.h) == "number",
		"show requires a numeric region"
	)
end

local function show_impl(item)
	validate_show_args(item)
	local session_id = item.session_id
	if runtime.failed_session_id ~= nil and runtime.failed_session_id ~= session_id then
		runtime.failed_session_id = nil
		runtime.failure_logged = false
	end
	if runtime.failed_session_id == session_id then
		return false
	end

	local region = copy_region(item.region)
	local mode = Model.normalizeMode(item.mode)
	local changed_session = runtime.session_id ~= session_id
	local changed_region = not same_region(runtime.region, region)
	local changed_mode = runtime.mode ~= mode
	local identical = not changed_session and not changed_region and not changed_mode
	if identical and (mode == "off" or runtime.active) then
		return true
	end

	if changed_session then
		release_visuals()
		runtime.trail = {}
		runtime.secure = false
		runtime.denied = false
		runtime.indicator = false
		runtime.failed_session_id = nil
		runtime.failure_logged = false
	elseif changed_mode then
		runtime.trail = {}
	end

	runtime.session_id = session_id
	runtime.region = region
	runtime.mode = mode

	local layout = Model.layout(region)
	if mode == "off" or not layout.visible then
		release_visuals()
		runtime.trail = {}
		return true
	end

	if runtime.active and changed_region then
		local canvas_layout = Model.layout(region)
		runtime.canvas:frame(canvas_layout.frame)
		redraw()
		return true
	end

	if not runtime.active then
		start_visuals()
	end
	redraw()
	return true
end

function M.show(item)
	local requested_session = type(item) == "table" and item.session_id or nil
	local ok, result = xpcall(function()
		return show_impl(item)
	end, traceback)
	if not ok then
		fail_session(requested_session or runtime.session_id, result)
		return false
	end
	return result
end

function M.setMode(mode)
	if type(runtime.session_id) ~= "string" or type(runtime.region) ~= "table" then
		return false
	end
	return M.show({ session_id = runtime.session_id, region = runtime.region, mode = mode })
end

function M.check()
	if runtime.tap and type(runtime.tap.isEnabled) == "function" and not runtime.tap:isEnabled() then
		runtime.tap:enable()
	end
	return M.isActive()
end

function M.isActive()
	return runtime.active == true
end

return M
