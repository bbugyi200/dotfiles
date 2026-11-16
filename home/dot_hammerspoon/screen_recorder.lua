-- Hammerspoon screen-recorder runtime.
--
-- Doctor inbox: SSH agents drop probe requests under
-- ~/tmp/screencasts/.macrec/requests/, this module validates them, draws an
-- opaque test card over the probe rectangle, and launches macrec_doctor run
-- via hs.task.
--
-- Live UI: executes screen_recording_model effects with selector, chrome,
-- menu bar, osascript notifications, clipboard guard, watchers, and re-adoption.
local Model = require("screen_recording_model")
local ScreenshotRegion = require("screenshot_region")
local MacNotify = require("mac_notify")

local M = {}

M.CHORD = Model.CHORD
M.ACCENT_HEX = Model.ACCENT
M.CARD_WIDTH = 240
M.CARD_HEIGHT = 150
M.CARD_INSET = 24
M.FRESH_SECONDS = 120
M.ALLOWED_PROBES = {
	env = true,
	capture = true,
	stop = true,
	cap = true,
	encode = true,
	detach = true,
	lifecycle = true,
}
M.TASK_PATH = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
-- Plan regex is ^[A-Za-z0-9_-]{1,64}$. Lua patterns have no {n,m} quantifier,
-- and a trailing `-]` range is unsafe, so length is checked separately.
M.ID_CHAR_PATTERN = "^[-A-Za-z0-9_]+$"
M.PROBE_SECONDS = {
	env = 2,
	capture = 6,
	stop = 16,
	cap = 6,
	encode = 90,
	detach = 5,
	lifecycle = 20,
}
M.SPINNER_FRAMES = { "◐", "◓", "◑", "◒" }

if type(BobScreenRecorder) ~= "table" then
	BobScreenRecorder = {}
end

local runtime = BobScreenRecorder
local unpackArgs = table.unpack or unpack

local dispatch
local apply_effects
local refresh_status
local render_menu
local ensure_tick
local ensure_poll
local ensure_spinner
local hide_recording_chrome
local show_recording_chrome
local redraw_chrome

local function log_message(format, ...)
	hs.printf("Bob screen recorder " .. format, ...)
end

local function stop_runtime_object(name, object)
	if not object then
		return
	end

	local ok, error_message = xpcall(function()
		if object.stop then
			object:stop()
		elseif object.terminate then
			object:terminate()
		elseif object.delete then
			object:delete()
		end
	end, debug.traceback)
	if not ok then
		log_message("could not stop previous %s: %s", name, error_message)
	end
end

local function dirname(path)
	return path:match("^(.*)/[^/]+$")
end

local function ensure_directory(path)
	if not path or path == "" or path == "/" then
		return true
	end
	local attrs_ok, attributes = pcall(function()
		return hs.fs.attributes(path)
	end)
	if attrs_ok and attributes then
		return true
	end
	local parent = dirname(path)
	if parent and parent ~= path then
		if not ensure_directory(parent) then
			return false
		end
	end
	local mkdir_ok, made = pcall(function()
		return hs.fs.mkdir(path)
	end)
	if mkdir_ok and made then
		return true
	end
	local retry_ok, retry_attrs = pcall(function()
		return hs.fs.attributes(path)
	end)
	return retry_ok and retry_attrs ~= nil
end

local function json_string(value)
	return '"' .. tostring(value):gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function refusal_json(id, reason)
	return string.format('{"schema":1,"id":%s,"refused":%s}\n', json_string(id), json_string(reason))
end

local function atomic_write(path, contents)
	local tmp = path .. ".tmp"
	local handle = io.open(tmp, "w")
	if not handle then
		log_message("could not open %s for writing", tmp)
		return false
	end
	handle:write(contents)
	handle:close()
	local renamed = os.rename(tmp, path)
	if not renamed then
		log_message("could not replace %s", path)
		pcall(os.remove, tmp)
		return false
	end
	return true
end

local function read_file(path)
	local handle = io.open(path, "r")
	if not handle then
		return nil
	end
	local text = handle:read("*a")
	handle:close()
	return text
end

function M.cardGeometry(screenFrame)
	return {
		x = screenFrame.x + screenFrame.w - M.CARD_INSET - M.CARD_WIDTH,
		y = screenFrame.y + screenFrame.h - M.CARD_INSET - M.CARD_HEIGHT,
		w = M.CARD_WIDTH,
		h = M.CARD_HEIGHT,
	}
end

function M.rectArg(rect)
	return string.format("%d,%d,%d,%d", rect.x, rect.y, rect.w, rect.h)
end

function M.parseProbes(value)
	local probes = {}
	if type(value) == "string" then
		for name in string.gmatch(value, "[^,]+") do
			table.insert(probes, name)
		end
		return probes
	end
	if type(value) ~= "table" then
		return nil
	end
	for _, name in ipairs(value) do
		if type(name) == "string" then
			table.insert(probes, name)
		end
	end
	return probes
end

function M.estimateSeconds(probes)
	local total = 0
	for _, name in ipairs(probes or {}) do
		total = total + (M.PROBE_SECONDS[name] or 5)
	end
	if total < 1 then
		total = 1
	end
	return total
end

function M.isValidId(id)
	return type(id) == "string" and #id >= 1 and #id <= 64 and id:match(M.ID_CHAR_PATTERN) ~= nil
end

function M.validateRequest(decoded, mtime, now, freshSeconds)
	freshSeconds = freshSeconds or M.FRESH_SECONDS
	if type(decoded) ~= "table" then
		return false, "invalid", nil, nil
	end
	if decoded.action ~= "doctor" then
		return false, "invalid", decoded.id, nil
	end
	local id = decoded.id
	if not M.isValidId(id) then
		return false, "invalid", id, nil
	end
	local probes = M.parseProbes(decoded.probes)
	if not probes or #probes == 0 then
		return false, "invalid", id, nil
	end
	for _, name in ipairs(probes) do
		if not M.ALLOWED_PROBES[name] then
			return false, "invalid", id, nil
		end
	end
	if type(mtime) ~= "number" or type(now) ~= "number" or (now - mtime) > freshSeconds then
		return false, "invalid", id, nil
	end
	return true, nil, id, probes
end

local function result_path(id)
	return runtime.doctorDir .. "/" .. id .. ".json"
end

local function write_refusal(id, reason)
	if not M.isValidId(id) then
		return
	end
	ensure_directory(runtime.doctorDir)
	atomic_write(result_path(id), refusal_json(id, reason))
end

local function session_locked()
	local ok, properties = pcall(function()
		return hs.caffeinate.sessionProperties()
	end)
	if not ok or type(properties) ~= "table" then
		return false
	end
	return properties.CGSSessionScreenIsLocked == true
end

local function main_screen_frame()
	local screen = hs.screen.mainScreen()
	if not screen or not screen.frame then
		return { x = 0, y = 0, w = 1440, h = 900 }
	end
	return screen:frame()
end

local function card_elements(flashOn)
	local fill = { hex = M.ACCENT_HEX, alpha = 1 }
	local white = { white = 1, alpha = flashOn and 1 or 0 }
	return {
		{
			type = "rectangle",
			action = "fill",
			frame = { x = 0, y = 0, w = M.CARD_WIDTH, h = M.CARD_HEIGHT },
			fillColor = fill,
		},
		{
			type = "text",
			action = "fill",
			frame = { x = 8, y = 18, w = M.CARD_WIDTH - 16, h = 28 },
			text = "macrec self-test",
			textColor = { white = 1, alpha = 0.98 },
			textFont = ".AppleSystemUIFont",
			textSize = 13,
			textAlignment = "center",
		},
		{
			type = "rectangle",
			action = "fill",
			id = "blink",
			frame = { x = (M.CARD_WIDTH - 40) / 2, y = 70, w = 40, h = 40 },
			fillColor = white,
		},
	}
end

local function hide_card()
	stop_runtime_object("blink timer", runtime.blinkTimer)
	runtime.blinkTimer = nil
	if runtime.card then
		pcall(function()
			runtime.card:hide(0)
		end)
		pcall(function()
			runtime.card:delete()
		end)
		runtime.card = nil
	end
end

local function show_card(frame)
	hide_card()
	local canvas = hs.canvas.new(frame)
	if not canvas then
		log_message("could not create test card canvas")
		return
	end
	runtime.cardFlashOn = true
	canvas:level("screenSaver")
	canvas:behaviorAsLabels({ "canJoinAllSpaces", "fullScreenAuxiliary" })
	canvas:clickActivating(false)
	canvas:replaceElements(unpackArgs(card_elements(true)))
	canvas:show()
	canvas:bringToFront(true)
	runtime.card = canvas
	runtime.blinkTimer = hs.timer.new(1, function()
		runtime.cardFlashOn = not runtime.cardFlashOn
		if runtime.card then
			runtime.card:replaceElements(unpackArgs(card_elements(runtime.cardFlashOn)))
		end
	end, true)
	runtime.blinkTimer:start()
end

local function show_notification(probes)
	local seconds = M.estimateSeconds(probes)
	local body = string.format("≈%d s · nothing leaves this Mac", seconds)
	MacNotify.post("Recording self-test running", "", body)
	runtime.lastNotification = {
		title = "Recording self-test running",
		body = body,
		seconds = seconds,
	}
end

local function task_running()
	local task = runtime.task
	if not task then
		return false
	end
	if task.isRunning then
		local ok, running = pcall(function()
			return task:isRunning()
		end)
		if ok then
			return running and true or false
		end
	end
	return runtime.busy == true
end

local function task_in_flight(task)
	if not task then
		return false
	end
	if type(task.isRunning) == "function" then
		local ok, running = pcall(function()
			return task:isRunning()
		end)
		if ok then
			return running and true or false
		end
	end
	return true
end

local function finish_task()
	runtime.task = nil
	runtime.busy = false
	hide_card()
end

local function launch_run(id, probes, keep)
	local rect = M.cardGeometry(main_screen_frame())
	show_card(rect)
	show_notification(probes)
	local argv = {
		"run",
		"--id",
		id,
		"--rect",
		M.rectArg(rect),
		"--probes",
		table.concat(probes, ","),
	}
	if keep then
		table.insert(argv, "--keep")
	end
	local task
	local on_complete = function()
		if runtime.task ~= task then
			return
		end
		finish_task()
	end
	task = hs.task.new(runtime.doctorPath, on_complete, argv)
	if not task then
		hide_card()
		write_refusal(id, "invalid")
		log_message("doctor task could not be created")
		return
	end
	if task.setEnvironment then
		task:setEnvironment({
			PATH = M.TASK_PATH,
			HOME = runtime.home,
		})
	end
	runtime.task = task
	runtime.busy = true
	runtime.lastTask = {
		command = runtime.doctorPath,
		args = argv,
		environment = {
			PATH = M.TASK_PATH,
			HOME = runtime.home,
		},
	}
	local start_ok, started = xpcall(function()
		return task:start()
	end, debug.traceback)
	if not start_ok or not started then
		runtime.task = nil
		runtime.busy = false
		hide_card()
		write_refusal(id, "invalid")
		if start_ok then
			log_message("doctor task could not be started")
		else
			log_message("doctor task start failed: %s", started)
		end
	end
end

local function handle_request_path(path)
	if type(path) ~= "string" or path == "" then
		return
	end
	if path:sub(-5) ~= ".json" or path:sub(-9) == ".json.tmp" then
		if hs.fs.attributes and hs.fs.attributes(path) and hs.fs.attributes(path).mode == "directory" then
			return
		end
		if not path:match("%.json$") then
			return
		end
	end

	local text = read_file(path)
	local attrs = hs.fs.attributes(path)
	pcall(os.remove, path)
	if not text then
		return
	end

	local decoded = nil
	if hs.json and hs.json.decode then
		local ok, value = pcall(hs.json.decode, text)
		if ok then
			decoded = value
		end
	end

	local mtime = attrs and attrs.modification or nil
	local now = runtime.nowFn()
	local valid, reason, id, probes = M.validateRequest(decoded, mtime, now, runtime.freshSeconds)
	if not id then
		id = path:match("doctor%-([-A-Za-z0-9_]+)%.json$")
	end
	if not valid then
		write_refusal(id, reason or "invalid")
		return
	end
	if session_locked() then
		write_refusal(id, "locked")
		return
	end
	if task_running() then
		write_refusal(id, "busy")
		return
	end
	local keep = type(decoded) == "table" and decoded.keep == true
	launch_run(id, probes, keep)
end

local function each_request_file(callback)
	local dir = runtime.requestsDir
	if type(hs.fs.dir) ~= "function" then
		return
	end
	local ok, iter, dir_obj = pcall(hs.fs.dir, dir)
	if not ok or type(iter) ~= "function" then
		return
	end
	for name in iter, dir_obj do
		if
			type(name) == "string"
			and name ~= "."
			and name ~= ".."
			and name:match("%.json$")
			and not name:match("%.tmp$")
		then
			callback(dir .. "/" .. name)
		end
	end
end

local function process_existing()
	each_request_file(handle_request_path)
end

local function on_path_event(paths)
	if type(paths) ~= "table" then
		process_existing()
		return
	end
	local saw_file = false
	for _, path in ipairs(paths) do
		if type(path) == "string" and path:match("%.json$") then
			saw_file = true
			handle_request_path(path)
		end
	end
	if not saw_file then
		process_existing()
	end
end

local function copy_rect(rect)
	if type(rect) ~= "table" then
		return nil
	end
	return {
		x = tonumber(rect.x) or 0,
		y = tonumber(rect.y) or 0,
		w = tonumber(rect.w) or 0,
		h = tonumber(rect.h) or 0,
	}
end

local function now_seconds()
	if type(runtime.nowFn) == "function" then
		return runtime.nowFn()
	end
	if hs.timer and type(hs.timer.secondsSinceEpoch) == "function" then
		local ok, value = pcall(hs.timer.secondsSinceEpoch)
		if ok and type(value) == "number" then
			return value
		end
	end
	return os.time()
end

local function pasteboard_count()
	if not hs.pasteboard or type(hs.pasteboard.changeCount) ~= "function" then
		return nil
	end
	local ok, count = pcall(hs.pasteboard.changeCount)
	if ok and type(count) == "number" then
		return count
	end
	return nil
end

local function decode_json(text)
	if type(text) ~= "string" or text == "" or not hs.json or type(hs.json.decode) ~= "function" then
		return nil
	end
	local ok, value = pcall(hs.json.decode, text)
	if ok then
		return value
	end
	return nil
end

local function screen_list()
	if not hs.screen or type(hs.screen.allScreens) ~= "function" then
		local main = hs.screen and hs.screen.mainScreen and hs.screen.mainScreen()
		if main then
			return { main }
		end
		return {}
	end
	local ok, screens = pcall(hs.screen.allScreens)
	if ok and type(screens) == "table" then
		return screens
	end
	return {}
end

local function screen_frame(screen)
	if not screen or type(screen.frame) ~= "function" then
		return nil
	end
	local ok, frame = pcall(function()
		return screen:frame()
	end)
	if ok then
		return frame
	end
	return nil
end

local function frame_contains_rect(frame, rect)
	return type(frame) == "table"
		and type(rect) == "table"
		and rect.x >= frame.x
		and rect.y >= frame.y
		and rect.x + rect.w <= frame.x + frame.w
		and rect.y + rect.h <= frame.y + frame.h
end

local function screen_for_region(region)
	if type(region) ~= "table" then
		return hs.screen and hs.screen.mainScreen and hs.screen.mainScreen() or nil
	end
	for _, screen in ipairs(screen_list()) do
		local frame = screen_frame(screen)
		if frame and frame_contains_rect(frame, region) then
			return screen
		end
	end
	return hs.screen and hs.screen.mainScreen and hs.screen.mainScreen() or nil
end

local function screen_id(screen)
	if not screen or type(screen.id) ~= "function" then
		return nil
	end
	local ok, value = pcall(function()
		return screen:id()
	end)
	if ok then
		return value
	end
	return nil
end

local function screen_name(screen)
	if not screen or type(screen.name) ~= "function" then
		return "Display"
	end
	local ok, value = pcall(function()
		return screen:name()
	end)
	if ok and type(value) == "string" and value ~= "" then
		return value
	end
	return "Display"
end

local function frames_equal(a, b)
	if type(a) ~= "table" or type(b) ~= "table" then
		return false
	end
	return a.x == b.x and a.y == b.y and a.w == b.w and a.h == b.h
end

local function to_local(rect, canvas_frame)
	return {
		x = rect.x - canvas_frame.x,
		y = rect.y - canvas_frame.y,
		w = rect.w,
		h = rect.h,
	}
end

local function union_frame(frames)
	local min_x, min_y, max_x, max_y
	for _, frame in ipairs(frames) do
		if type(frame) == "table" then
			local x2 = frame.x + frame.w
			local y2 = frame.y + frame.h
			min_x = min_x and math.min(min_x, frame.x) or frame.x
			min_y = min_y and math.min(min_y, frame.y) or frame.y
			max_x = max_x and math.max(max_x, x2) or x2
			max_y = max_y and math.max(max_y, y2) or y2
		end
	end
	if not min_x then
		return nil
	end
	return { x = min_x, y = min_y, w = max_x - min_x, h = max_y - min_y }
end

local function track_cli_task(task)
	runtime.cliTasks = runtime.cliTasks or {}
	if task then
		table.insert(runtime.cliTasks, task)
	end
	return task
end

local function run_macrec(args, on_complete)
	local task
	local callback = function(exit_code, stdout, stderr)
		if on_complete then
			on_complete(exit_code, stdout, stderr)
		end
	end
	task = hs.task.new(runtime.macrecPath, callback, args)
	if not task then
		log_message("macrec task could not be created")
		if on_complete then
			on_complete(1, "", "could not create task")
		end
		return nil
	end
	if task.setEnvironment then
		task:setEnvironment({
			PATH = M.TASK_PATH,
			HOME = runtime.home,
		})
	end
	track_cli_task(task)
	runtime.lastMacrec = {
		command = runtime.macrecPath,
		args = args,
		environment = {
			PATH = M.TASK_PATH,
			HOME = runtime.home,
		},
	}
	local start_ok, started = xpcall(function()
		return task:start()
	end, debug.traceback)
	if not start_ok or not started then
		if start_ok then
			log_message("macrec task could not be started")
		else
			log_message("macrec task start failed: %s", started)
		end
		if on_complete then
			on_complete(1, "", start_ok and "could not start task" or tostring(started))
		end
		return nil
	end
	return task
end

local function open_path(path, edit)
	if type(path) ~= "string" or path == "" then
		return
	end
	local args = edit and { "-t", path } or { path }
	local task = hs.task.new("/usr/bin/open", function() end, args)
	if task then
		if task.setEnvironment then
			task:setEnvironment({
				PATH = M.TASK_PATH,
				HOME = runtime.home,
			})
		end
		track_cli_task(task)
		pcall(function()
			task:start()
		end)
	end
end

local function copy_path(path)
	if type(path) ~= "string" or not hs.pasteboard or type(hs.pasteboard.setContents) ~= "function" then
		return
	end
	pcall(hs.pasteboard.setContents, path)
end

local function read_reduce_motion()
	if type(hs.execute) ~= "function" then
		return false
	end
	local ok, output = pcall(hs.execute, "/usr/bin/defaults read com.apple.universalaccess reduceMotion")
	if not ok or type(output) ~= "string" then
		return false
	end
	return tonumber(output:match("%d+")) == 1
end

local function event_flag(flags, name)
	return type(flags) == "table" and flags[name] == true
end

local function is_event_object(event)
	local kind = type(event)
	return kind == "table" or kind == "userdata"
end

local function event_matches_chord(event)
	if not is_event_object(event) then
		return false
	end
	local flags = {}
	if type(event.getFlags) == "function" then
		local ok, value = pcall(function()
			return event:getFlags()
		end)
		if ok and type(value) == "table" then
			flags = value
		end
	end
	local needed = {}
	for _, name in ipairs(Model.CHORD.mods) do
		needed[name] = true
	end
	for _, name in ipairs({ "cmd", "ctrl", "alt", "shift", "fn" }) do
		if event_flag(flags, name) ~= (needed[name] == true) then
			return false
		end
	end
	local want = Model.CHORD.key
	if type(event.getCharacters) == "function" then
		local ok, chars = pcall(function()
			return event:getCharacters()
		end)
		if ok and type(chars) == "string" and chars:lower() == want then
			return true
		end
	end
	if type(event.getKeyCode) == "function" and hs.keycodes and hs.keycodes.map then
		local ok, code = pcall(function()
			return event:getKeyCode()
		end)
		if ok and code == hs.keycodes.map[want] then
			return true
		end
	end
	return false
end

local function event_matches_still_chord(event)
	if not is_event_object(event) then
		return false
	end
	local flags = {}
	if type(event.getFlags) == "function" then
		local ok, value = pcall(function()
			return event:getFlags()
		end)
		if ok and type(value) == "table" then
			flags = value
		end
	end
	if
		type(flags) ~= "table"
		or flags.ctrl ~= true
		or flags.alt ~= true
		or flags.shift ~= true
		or flags.cmd
		or flags.fn
	then
		return false
	end
	if type(event.getCharacters) == "function" then
		local ok, chars = pcall(function()
			return event:getCharacters()
		end)
		if ok and type(chars) == "string" and chars:lower() == "s" then
			return true
		end
	end
	if type(event.getKeyCode) == "function" and hs.keycodes and hs.keycodes.map then
		local ok, code = pcall(function()
			return event:getKeyCode()
		end)
		return ok and code == hs.keycodes.map.s
	end
	return false
end

local function event_is_repeat(event)
	if not is_event_object(event) then
		return false
	end
	if event["repeat"] == true then
		return true
	end
	if type(event.getProperty) == "function" and hs.eventtap and hs.eventtap.event and hs.eventtap.event.properties then
		local key = hs.eventtap.event.properties.keyboardEventAutorepeat
		if key ~= nil then
			local ok, value = pcall(function()
				return event:getProperty(key)
			end)
			if ok and (value == 1 or value == true) then
				return true
			end
		end
	end
	return false
end

local function event_is_m(event)
	if not is_event_object(event) then
		return false
	end
	if type(event.getCharacters) == "function" then
		local ok, chars = pcall(function()
			return event:getCharacters()
		end)
		if ok and type(chars) == "string" and chars:lower() == "m" then
			return true
		end
	end
	if type(event.getKeyCode) == "function" and hs.keycodes and hs.keycodes.map then
		local ok, code = pcall(function()
			return event:getKeyCode()
		end)
		if ok and code == hs.keycodes.map.m then
			return true
		end
	end
	return false
end

local function close_selector()
	local handle = runtime.pickerHandle
	runtime.pickerHandle = nil
	if handle and type(handle.cancel) == "function" then
		pcall(handle.cancel)
	end
end

local function open_selector()
	runtime.pickerState = { mic = false }
	local handle = ScreenshotRegion.pick(function(region)
		dispatch({
			type = "enter",
			region = copy_rect(region),
			mic = runtime.pickerState and runtime.pickerState.mic == true,
		})
	end, {
		accent = { hex = Model.ACCENT, alpha = 1 },
		badge = function(state)
			return (state and state.mic == true) and "● REC · MIC" or "● REC"
		end,
		hint = function(state)
			return Model.selectorHint(state)
		end,
		settingsKey = Model.SETTINGS_KEY,
		fallbackSettingsKey = Model.FALLBACK_SETTINGS_KEY,
		state = runtime.pickerState,
		captureDelay = 0.15,
		onKey = function(event, ctx)
			if event_is_m(event) then
				ctx.state.mic = not ctx.state.mic
				ctx.redraw()
				return true
			end
			if event_matches_still_chord(event) then
				local region = ctx.region()
				ctx.cancel()
				if type(M.captureStill) == "function" then
					M.captureStill(region)
				end
				return true
			end
			if event_matches_chord(event) then
				M.onChord(event)
				return true
			end
		end,
		onCancel = function(reason)
			runtime.pickerHandle = nil
			dispatch({ type = "picker_cancel", reason = reason })
		end,
	})
	runtime.pickerHandle = handle
end

local function stop_chrome_timers()
	stop_runtime_object("breath timer", runtime.breathTimer)
	stop_runtime_object("pill blink timer", runtime.pillBlinkTimer)
	stop_runtime_object("shutter timer", runtime.shutterTimer)
	runtime.breathTimer = nil
	runtime.pillBlinkTimer = nil
	runtime.shutterTimer = nil
end

hide_recording_chrome = function()
	stop_chrome_timers()
	for _, entry in ipairs(runtime.chromeCanvases or {}) do
		local canvas = entry.canvas or entry
		pcall(function()
			canvas:hide(0)
		end)
		pcall(function()
			canvas:delete()
		end)
	end
	runtime.chromeCanvases = {}
	runtime.chromeLayout = nil
	runtime.chromeSession = nil
	runtime.chromeScreenId = nil
	runtime.chromeScreenFrame = nil
	runtime.breathPhase = 0
	runtime.pillBlinkOn = true
	runtime.shutterFlash = false
end

local function breath_alpha()
	if runtime.reduceMotion or runtime.shutterFlash then
		return 1
	end
	local phase = runtime.breathPhase or 0
	return 0.8 + 0.2 * math.cos(math.pi * phase)
end

local function accent_color(alpha)
	if runtime.shutterFlash then
		return { white = 1, alpha = alpha or 1 }
	end
	return { hex = Model.ACCENT, alpha = alpha or 1 }
end

local function canvas_frame(canvas)
	if not canvas then
		return nil
	end
	if type(canvas.frame) == "function" then
		local ok, frame = pcall(function()
			return canvas:frame()
		end)
		if ok then
			return frame
		end
	end
	return canvas.frame
end

local function new_chrome_canvas(frame, kind)
	local canvas = hs.canvas.new(frame)
	if not canvas then
		return nil
	end
	canvas:level("overlay")
	canvas:behaviorAsLabels({ "canJoinAllSpaces", "fullScreenAuxiliary" })
	canvas:clickActivating(false)
	canvas:show()
	canvas:bringToFront(true)
	table.insert(runtime.chromeCanvases, {
		canvas = canvas,
		kind = kind,
		frame = copy_rect(frame),
	})
	return canvas
end

local function bracket_elements(brackets, canvas_frame, alpha)
	local elements = {}
	local color = accent_color(alpha)
	for _, bracket in ipairs(brackets or {}) do
		local local_frame = to_local(bracket, canvas_frame)
		if
			local_frame.x + local_frame.w >= -1
			and local_frame.y + local_frame.h >= -1
			and local_frame.x <= canvas_frame.w + 1
			and local_frame.y <= canvas_frame.h + 1
		then
			if bracket.axis == "horizontal" then
				table.insert(elements, {
					type = "segments",
					action = "stroke",
					strokeColor = color,
					strokeWidth = bracket.h,
					strokeCapStyle = "round",
					coordinates = {
						{ x = local_frame.x, y = local_frame.y + local_frame.h / 2 },
						{ x = local_frame.x + local_frame.w, y = local_frame.y + local_frame.h / 2 },
					},
				})
			else
				table.insert(elements, {
					type = "segments",
					action = "stroke",
					strokeColor = color,
					strokeWidth = bracket.w,
					strokeCapStyle = "round",
					coordinates = {
						{ x = local_frame.x + local_frame.w / 2, y = local_frame.y },
						{ x = local_frame.x + local_frame.w / 2, y = local_frame.y + local_frame.h },
					},
				})
			end
		end
	end
	return elements
end

local function hairline_element(strip, canvas_frame)
	return {
		type = "rectangle",
		action = "fill",
		frame = to_local(strip, canvas_frame),
		fillColor = { hex = Model.ACCENT, alpha = 0.7 },
	}
end

local function pill_elements(session, canvas_frame)
	local elapsed = 0
	if session and type(session.started_at) == "number" then
		elapsed = math.max(0, now_seconds() - session.started_at)
	end
	local dot = (runtime.reduceMotion or runtime.pillBlinkOn) and "●" or " "
	local text = string.format("%s %s  %s to stop", dot, Model.formatElapsed(elapsed), Model.CHORD_LABEL)
	return {
		{
			type = "rectangle",
			action = "fill",
			frame = { x = 0, y = 0, w = canvas_frame.w, h = canvas_frame.h },
			fillColor = { white = 0, alpha = 0.72 },
			roundedCorners = true,
			radius = 8,
		},
		{
			type = "text",
			action = "fill",
			frame = { x = 8, y = 5, w = canvas_frame.w - 16, h = canvas_frame.h - 10 },
			text = text,
			textColor = { white = 1, alpha = 0.98 },
			textFont = ".AppleSystemUIFont",
			textSize = 12,
			textAlignment = "center",
		},
	}
end

redraw_chrome = function()
	local layout = runtime.chromeLayout
	local canvases = runtime.chromeCanvases or {}
	if not layout or #canvases == 0 then
		return
	end
	local alpha = breath_alpha()
	local strips = layout.strips or {}
	for _, entry in ipairs(canvases) do
		local canvas = entry.canvas or entry
		local frame = entry.frame or canvas_frame(canvas)
		if canvas and frame then
			local elements
			if entry.kind == "top" and strips.top then
				elements = { hairline_element(strips.top, frame) }
				for _, element in ipairs(bracket_elements(layout.brackets, frame, alpha)) do
					table.insert(elements, element)
				end
			elseif entry.kind == "bottom" and strips.bottom then
				elements = { hairline_element(strips.bottom, frame) }
				for _, element in ipairs(bracket_elements(layout.brackets, frame, alpha)) do
					table.insert(elements, element)
				end
			elseif entry.kind == "left" and strips.left then
				elements = { hairline_element(strips.left, frame) }
			elseif entry.kind == "right" and strips.right then
				elements = { hairline_element(strips.right, frame) }
			elseif entry.kind == "pill" then
				elements = pill_elements(runtime.chromeSession, frame)
			end
			if elements then
				canvas:replaceElements(unpackArgs(elements))
			end
		end
	end
end

local function start_chrome_animations()
	stop_runtime_object("breath timer", runtime.breathTimer)
	stop_runtime_object("pill blink timer", runtime.pillBlinkTimer)
	runtime.breathTimer = nil
	runtime.pillBlinkTimer = nil
	if runtime.reduceMotion then
		return
	end
	runtime.breathPhase = 0
	runtime.breathTimer = hs.timer.new(0.1, function()
		runtime.breathPhase = (runtime.breathPhase or 0) + 0.1
		redraw_chrome()
	end, true)
	runtime.breathTimer:start()
	runtime.pillBlinkOn = true
	runtime.pillBlinkTimer = hs.timer.new(1, function()
		runtime.pillBlinkOn = not runtime.pillBlinkOn
		redraw_chrome()
	end, true)
	runtime.pillBlinkTimer:start()
end

show_recording_chrome = function(session)
	hide_recording_chrome()
	session = session or {}
	runtime.chromeSession = session
	runtime.reduceMotion = read_reduce_motion()
	local region = session.region
	local screen = screen_for_region(region)
	local frame = screen_frame(screen) or main_screen_frame()
	runtime.chromeScreenId = screen_id(screen)
	runtime.chromeScreenFrame = copy_rect(frame)
	local layout = Model.chromeLayout(region, frame)
	runtime.chromeLayout = layout
	local strips = layout.strips or {}
	local top_frame = union_frame({
		strips.top,
		layout.brackets and layout.brackets[1],
		layout.brackets and layout.brackets[2],
		layout.brackets and layout.brackets[3],
		layout.brackets and layout.brackets[4],
	})
	local bottom_frame = union_frame({
		strips.bottom,
		layout.brackets and layout.brackets[5],
		layout.brackets and layout.brackets[6],
		layout.brackets and layout.brackets[7],
		layout.brackets and layout.brackets[8],
	})
	if top_frame then
		new_chrome_canvas(top_frame, "top")
	end
	if bottom_frame then
		new_chrome_canvas(bottom_frame, "bottom")
	end
	if strips.left then
		new_chrome_canvas(strips.left, "left")
	end
	if strips.right then
		new_chrome_canvas(strips.right, "right")
	end
	if layout.pill and layout.pill.frame then
		new_chrome_canvas(layout.pill.frame, "pill")
	end
	redraw_chrome()
	start_chrome_animations()
end

local function flash_shutter()
	if runtime.reduceMotion then
		hide_recording_chrome()
		return
	end
	runtime.shutterFlash = true
	redraw_chrome()
	stop_runtime_object("shutter timer", runtime.shutterTimer)
	runtime.shutterTimer = hs.timer.doAfter(0.12, function()
		runtime.shutterFlash = false
		local canvases = runtime.chromeCanvases or {}
		for _, entry in ipairs(canvases) do
			local canvas = entry.canvas or entry
			pcall(function()
				canvas:hide(0.2)
			end)
		end
		runtime.shutterTimer = hs.timer.doAfter(0.2, function()
			hide_recording_chrome()
		end)
	end)
end

local function non_terminal_state(state)
	return state == Model.STATES.starting
		or state == Model.STATES.recording
		or state == Model.STATES.stopping
		or state == Model.STATES.shipping
end

ensure_tick = function()
	if runtime.model and runtime.model.state == Model.STATES.recording then
		if not runtime.tickTimer then
			runtime.tickTimer = hs.timer.new(1, function()
				dispatch({ type = "tick", change_count = pasteboard_count() })
				redraw_chrome()
			end, true)
			runtime.tickTimer:start()
		end
	else
		stop_runtime_object("tick timer", runtime.tickTimer)
		runtime.tickTimer = nil
	end
end

ensure_poll = function()
	if runtime.model and non_terminal_state(runtime.model.state) then
		if not runtime.pollTimer then
			runtime.pollTimer = hs.timer.new(1, function()
				refresh_status()
			end, true)
			runtime.pollTimer:start()
		end
	else
		stop_runtime_object("poll timer", runtime.pollTimer)
		runtime.pollTimer = nil
	end
end

ensure_spinner = function()
	local state = runtime.model and runtime.model.state
	local spinning = (state == Model.STATES.stopping or state == Model.STATES.shipping) and not runtime.reduceMotion
	if spinning then
		if not runtime.spinnerTimer then
			runtime.spinnerIndex = 1
			runtime.spinnerTimer = hs.timer.new(0.25, function()
				runtime.spinnerIndex = (runtime.spinnerIndex or 1) % #M.SPINNER_FRAMES + 1
				render_menu()
			end, true)
			runtime.spinnerTimer:start()
		end
	else
		stop_runtime_object("spinner timer", runtime.spinnerTimer)
		runtime.spinnerTimer = nil
	end
end

local function schedule_done_clear()
	stop_runtime_object("done timer", runtime.doneTimer)
	runtime.doneTimer = hs.timer.doAfter(3, function()
		if runtime.model and runtime.model.state == Model.STATES.done then
			runtime.model.state = Model.STATES.idle
			render_menu()
		end
	end)
end

local function valid_font(font)
	if type(font) ~= "table" or type(font.name) ~= "string" or font.name == "" then
		return nil
	end
	if type(hs.styledtext) ~= "table" or type(hs.styledtext.validFont) ~= "function" then
		return font
	end
	if not hs.styledtext.validFont(font.name) then
		return nil
	end
	return font
end

local function menu_font()
	if runtime.menuFont then
		return runtime.menuFont
	end
	local menu_bar = hs.styledtext and hs.styledtext.defaultFonts and hs.styledtext.defaultFonts.menuBar
	for _, name in ipairs({ "Menlo-Regular", "Menlo", "Monaco" }) do
		local font = { name = name }
		if type(menu_bar) == "table" and menu_bar.size then
			font.size = menu_bar.size
		end
		local valid = valid_font(font)
		if valid then
			runtime.menuFont = valid
			return valid
		end
	end
	runtime.menuFont = menu_bar
	return runtime.menuFont
end

local function color_for_role(role)
	if role == "warn" then
		return { hex = Model.WARN, alpha = 1 }
	end
	if role == "ok" then
		return { hex = Model.OK, alpha = 1 }
	end
	if role == "accent" or role == "shipping" then
		return { hex = Model.ACCENT, alpha = 1 }
	end
	return { list = "System", name = "labelColor", alpha = 1 }
end

local function compose_title(segments)
	if type(segments) ~= "table" or #segments == 0 then
		return ""
	end
	if type(hs.styledtext) ~= "table" or type(hs.styledtext.new) ~= "function" then
		local parts = {}
		for _, segment in ipairs(segments) do
			table.insert(parts, tostring(segment.text or ""))
		end
		return table.concat(parts)
	end
	local composed = nil
	local font = menu_font()
	for _, segment in ipairs(segments) do
		local styled = hs.styledtext.new(tostring(segment.text or ""), {
			color = color_for_role(segment.role),
			font = font,
		})
		if composed == nil then
			composed = styled
		else
			composed = composed .. styled
		end
	end
	return composed or ""
end

local function shipping_count()
	local count = runtime.model and runtime.model.shipping_count
	if type(count) == "number" and count > 0 then
		return count
	end
	return 1
end

local function menu_segments()
	local model = runtime.model or { state = Model.STATES.idle }
	local segments = Model.menuTitle({
		state = model.state,
		session = model.session,
		shipping_count = shipping_count(),
	}, now_seconds())
	if runtime.spinnerTimer and type(segments) == "table" and segments[1] then
		local frame = M.SPINNER_FRAMES[runtime.spinnerIndex or 1] or "◐"
		segments = {
			{ text = frame .. " " .. tostring(segments[1].text or ""), role = segments[1].role },
		}
	end
	return segments
end

local function session_path()
	local session = runtime.model and runtime.model.session or {}
	return session.mp4 or session.path
end

local function session_log()
	local session = runtime.model and runtime.model.session or {}
	return session.log
end

local function confirm_discard()
	local elapsed = Model.formatElapsed(0)
	local session = runtime.model and runtime.model.session
	if session and type(session.started_at) == "number" then
		elapsed = Model.formatElapsed(math.max(0, now_seconds() - session.started_at))
	end
	local message = elapsed .. " will be deleted and nothing uploaded."
	local button = "Keep Recording"
	if hs.dialog and type(hs.dialog.blockAlert) == "function" then
		local ok, result = pcall(hs.dialog.blockAlert, "Discard this recording?", message, "Discard", "Keep Recording")
		if ok and type(result) == "string" then
			button = result
		end
	end
	if button == "Discard" then
		dispatch({ type = "discard_confirmed", change_count = pasteboard_count() })
	end
end

local function handle_menu_action(action)
	if action == "stop_upload" then
		dispatch({ type = "stop", reason = "menu", change_count = pasteboard_count() })
	elseif action == "discard" then
		confirm_discard()
	elseif action == "cancel" then
		M.onChord()
	elseif action == "retry" then
		local id = runtime.model and runtime.model.session and runtime.model.session.id
		if id then
			run_macrec({ "retry", id }, function()
				refresh_status()
			end)
		end
	elseif action == "reveal" then
		open_path(session_path())
	elseif action == "show_log" then
		open_path(session_log(), true)
	elseif action == "dismiss" then
		local id = runtime.model and runtime.model.session and runtime.model.session.id
		if runtime.model then
			runtime.model.state = Model.STATES.idle
		end
		render_menu()
		-- Persist the dismissal so the next status refresh or reload does not
		-- resurface the same failure.
		if id then
			run_macrec({ "ack", id, "dismissed" }, function()
				refresh_status()
			end)
		end
	end
end

local function build_menu_items()
	local model = runtime.model or { state = Model.STATES.idle }
	local rows = Model.menuItems({
		state = model.state,
		session = model.session,
	}, now_seconds())
	local items = {}
	for _, row in ipairs(rows or {}) do
		local title = ""
		if type(row.segments) == "table" and row.segments[1] then
			title = tostring(row.segments[1].text or "")
		end
		local item = { title = title }
		if row.enabled == false or not row.action then
			item.disabled = true
		else
			local action = row.action
			item.fn = function()
				handle_menu_action(action)
			end
		end
		table.insert(items, item)
	end
	return items
end

render_menu = function()
	local menu = runtime.menu
	if not menu then
		return
	end
	local state = runtime.model and runtime.model.state or Model.STATES.idle
	if state == Model.STATES.idle or state == Model.STATES.selecting then
		if menu.removeFromMenuBar then
			menu:removeFromMenuBar()
		end
		if menu.setTitle then
			menu:setTitle("")
		end
		return
	end
	local segments = menu_segments()
	if type(segments) ~= "table" or #segments == 0 then
		if menu.removeFromMenuBar then
			menu:removeFromMenuBar()
		end
		return
	end
	if menu.setTitle then
		menu:setTitle(compose_title(segments))
	end
	if menu.returnToMenuBar then
		menu:returnToMenuBar()
	end
	if state == Model.STATES.done then
		schedule_done_clear()
	else
		stop_runtime_object("done timer", runtime.doneTimer)
		runtime.doneTimer = nil
	end
end

local function show_session_notification(item)
	local notification = item.notification or {}
	-- Hammerspoon's notify API is silently accepted but not presented here.
	-- Ack only after osascript exits successfully; macrec_ship owns fallback.
	MacNotify.post(
		notification.title or "Recording uploaded",
		notification.subtitle or "",
		notification.body or "",
		function(ok)
			if ok and item.session_id then
				run_macrec({ "ack", item.session_id, "notified" })
			end
		end
	)
	runtime.lastRecordingNotification = notification
end

local function start_recorder(item)
	local region = item.region or {}
	local args = { "start", M.rectArg(region) }
	if item.mic == true then
		table.insert(args, "--mic")
	end
	table.insert(args, "--max-seconds")
	table.insert(args, tostring(item.max_seconds or Model.CAP_SECONDS))
	local display = screen_name(screen_for_region(region))
	runtime.startTask = run_macrec(args, function(exit_code, stdout, stderr)
		runtime.startTask = nil
		if exit_code == 0 then
			local decoded = decode_json(stdout) or {}
			decoded.region = decoded.region or copy_rect(region)
			decoded.mic = decoded.mic
			if decoded.mic == nil then
				decoded.mic = item.mic == true
			end
			decoded.display_name = display
			dispatch({ type = "start_ok", session = decoded, id = decoded.id })
		else
			local reason = tostring(stderr or "")
			reason = reason:gsub("^%s+", ""):gsub("%s+$", "")
			if reason == "" then
				reason = "The recorder failed to start."
			end
			dispatch({ type = "start_fail", reason = reason })
		end
	end)
end

local function stop_recorder(item)
	local args = { "stop" }
	if item and item.reason then
		table.insert(args, "--reason")
		table.insert(args, item.reason)
	end
	runtime.stopTask = run_macrec(args, function()
		runtime.stopTask = nil
		dispatch({ type = "stop_done", change_count = pasteboard_count() })
	end)
end

apply_effects = function(effects)
	local hide = false
	local flash = false
	for _, item in ipairs(effects or {}) do
		local kind = item.type
		if kind == "hide_chrome" then
			hide = true
		elseif kind == "flash_shutter" then
			flash = true
		elseif kind == "open_selector" then
			open_selector()
		elseif kind == "close_selector" then
			close_selector()
		elseif kind == "start_recorder" then
			start_recorder(item)
		elseif kind == "stop_recorder" then
			stop_recorder(item)
		elseif kind == "discard" then
			run_macrec({ "discard" })
		elseif kind == "show_chrome" then
			show_recording_chrome(item.session)
		elseif kind == "notify" then
			show_session_notification(item)
		elseif kind == "copy_path" then
			copy_path(item.path)
		elseif kind == "ack" then
			if item.session_id and item.kind then
				run_macrec({ "ack", item.session_id, item.kind })
			end
		elseif kind == "recover" then
			if item.session_id then
				run_macrec({ "recover", item.session_id })
			end
		end
	end
	if flash then
		flash_shutter()
	elseif hide then
		hide_recording_chrome()
	end
	render_menu()
	ensure_tick()
	ensure_poll()
	ensure_spinner()
end

dispatch = function(event)
	if runtime.tearingDown then
		return
	end
	local model, effects = Model.reduce(runtime.model, event, now_seconds())
	runtime.model = model
	apply_effects(effects)
end

local function maybe_ack_adopted(status)
	local active = status and status.active
	if type(active) ~= "table" or type(active.id) ~= "string" then
		return
	end
	if active.state ~= "recording" then
		return
	end
	runtime.adoptedIds = runtime.adoptedIds or {}
	if runtime.adoptedIds[active.id] then
		return
	end
	runtime.adoptedIds[active.id] = true
	run_macrec({ "ack", active.id, "adopted" })
end

local function adopt_unbound_sessions(status)
	if not runtime.model or runtime.model.state ~= Model.STATES.idle then
		return
	end
	status = Model.userStatus(status) or {}
	for _, session in ipairs(status.sessions or {}) do
		local session_status = session.status
		if session_status == "finalizing" or session_status == "encoding" or session_status == "uploading" then
			runtime.model.state = Model.STATES.shipping
			runtime.model.session = session
			render_menu()
			ensure_poll()
			ensure_spinner()
			return
		end
	end
	for _, session in ipairs(status.sessions or {}) do
		if session.status == "failed" and not Model.isDismissed(session) then
			runtime.model.state = Model.STATES.failed
			runtime.model.session = session
			render_menu()
			return
		end
	end
end

refresh_status = function()
	if task_in_flight(runtime.statusTask) then
		return
	end
	runtime.statusTask = run_macrec({ "status", "--json" }, function(exit_code, stdout, _stderr)
		runtime.statusTask = nil
		local decoded = exit_code == 0 and decode_json(stdout) or nil
		local status = Model.parseStatus(decoded)
		dispatch({
			type = "status_refresh",
			status = status,
			clipboard_change_count = pasteboard_count(),
			context = {},
		})
		adopt_unbound_sessions(status)
		maybe_ack_adopted(status)
	end)
end

local function on_status_path_event(paths)
	if type(paths) == "table" then
		local relevant = false
		for _, path in ipairs(paths) do
			if
				type(path) == "string"
				and not path:find("/requests/", 1, true)
				and not path:find("/doctor/", 1, true)
			then
				relevant = true
				break
			end
		end
		if not relevant then
			return
		end
	end
	if runtime.statusDebounce and type(runtime.statusDebounce.start) == "function" then
		runtime.statusDebounce:start()
	else
		refresh_status()
	end
end

local function check_display()
	if not runtime.model or runtime.model.state ~= Model.STATES.recording then
		return
	end
	local region = runtime.model.session and runtime.model.session.region
	local screen = screen_for_region(region)
	if not screen then
		dispatch({ type = "display_loss", change_count = pasteboard_count() })
		return
	end
	local id = screen_id(screen)
	local frame = screen_frame(screen)
	if
		(runtime.chromeScreenId ~= nil and id ~= runtime.chromeScreenId)
		or not frames_equal(frame, runtime.chromeScreenFrame)
	then
		dispatch({ type = "display_loss", change_count = pasteboard_count() })
	end
end

local function on_caffeinate_event(event_type)
	local watcher = hs.caffeinate and hs.caffeinate.watcher
	if not watcher then
		return
	end
	if event_type == watcher.systemWillSleep then
		dispatch({ type = "sleep", change_count = pasteboard_count() })
	elseif event_type == watcher.screensDidLock then
		dispatch({ type = "lock", change_count = pasteboard_count() })
	elseif event_type == watcher.systemWillPowerOff then
		dispatch({ type = "stop", reason = "system", change_count = pasteboard_count() })
	end
end

local function menu_builder()
	local ok, items = xpcall(build_menu_items, debug.traceback)
	if not ok then
		log_message("menu failed: %s", items)
		return {}
	end
	return items
end

local function teardown_runtime()
	runtime.tearingDown = true
	close_selector()
	stop_runtime_object("path watcher", runtime.watcher)
	stop_runtime_object("status watcher", runtime.statusWatcher)
	stop_runtime_object("status debounce", runtime.statusDebounce)
	stop_runtime_object("doctor task", runtime.task)
	stop_runtime_object("caffeinate watcher", runtime.caffeineWatcher)
	stop_runtime_object("screen watcher", runtime.screenWatcher)
	stop_runtime_object("tick timer", runtime.tickTimer)
	stop_runtime_object("poll timer", runtime.pollTimer)
	stop_runtime_object("spinner timer", runtime.spinnerTimer)
	stop_runtime_object("done timer", runtime.doneTimer)
	for _, task in ipairs(runtime.cliTasks or {}) do
		stop_runtime_object("macrec task", task)
	end
	hide_recording_chrome()
	hide_card()
	runtime.watcher = nil
	runtime.statusWatcher = nil
	runtime.statusDebounce = nil
	runtime.task = nil
	runtime.busy = false
	runtime.blinkTimer = nil
	runtime.caffeineWatcher = nil
	runtime.screenWatcher = nil
	runtime.tickTimer = nil
	runtime.pollTimer = nil
	runtime.spinnerTimer = nil
	runtime.doneTimer = nil
	runtime.cliTasks = {}
	runtime.statusTask = nil
	runtime.startTask = nil
	runtime.stopTask = nil
	runtime.tearingDown = false
end

function M.onChord(event)
	dispatch({
		type = "chord",
		change_count = pasteboard_count(),
		["repeat"] = event_is_repeat(event),
	})
end

function M.isChordEvent(event)
	return event_matches_chord(event)
end

function M.isStillChordEvent(event)
	return event_matches_still_chord(event)
end

function M.startRegion(region)
	M.onChord()
	dispatch({ type = "enter", region = copy_rect(region), mic = false })
end

function M.start(options)
	options = options or {}
	runtime.home = options.home or os.getenv("HOME") or ""
	runtime.doctorPath = options.doctor_path or (runtime.home .. "/bin/macrec_doctor")
	runtime.macrecPath = options.macrec_path or (runtime.home .. "/bin/macrec")
	runtime.nowFn = options.now or os.time
	runtime.freshSeconds = options.fresh_seconds or M.FRESH_SECONDS
	runtime.macrecDir = runtime.home .. "/tmp/screencasts/.macrec"
	runtime.requestsDir = runtime.macrecDir .. "/requests"
	runtime.doctorDir = runtime.macrecDir .. "/doctor"

	teardown_runtime()
	runtime.model = { state = Model.STATES.idle, session = {} }
	runtime.adoptedIds = {}
	runtime.pickerState = { mic = false }
	runtime.menuFont = nil
	runtime.reduceMotion = false
	runtime.spinnerIndex = 1

	ensure_directory(runtime.requestsDir)
	ensure_directory(runtime.doctorDir)
	pcall(os.execute, string.format("chmod 700 %q %q", runtime.requestsDir, runtime.doctorDir))

	runtime.menu = runtime.menu or hs.menubar.new(false, "BobScreenRecorder")
	if runtime.menu and runtime.menu.setMenu then
		runtime.menu:setMenu(menu_builder)
	end
	render_menu()

	local watcher = hs.pathwatcher.new(runtime.requestsDir, function(paths)
		on_path_event(paths)
	end)
	if watcher then
		watcher:start()
		runtime.watcher = watcher
	else
		log_message("path watcher could not be created")
	end

	if hs.timer and hs.timer.delayed and type(hs.timer.delayed.new) == "function" then
		runtime.statusDebounce = hs.timer.delayed.new(0.1, function()
			refresh_status()
		end)
	end
	local status_watcher = hs.pathwatcher.new(runtime.macrecDir, function(paths)
		on_status_path_event(paths)
	end)
	if status_watcher then
		status_watcher:start()
		runtime.statusWatcher = status_watcher
	end

	if hs.caffeinate and hs.caffeinate.watcher and type(hs.caffeinate.watcher.new) == "function" then
		runtime.caffeineWatcher = hs.caffeinate.watcher.new(function(event_type)
			on_caffeinate_event(event_type)
		end)
		if runtime.caffeineWatcher and runtime.caffeineWatcher.start then
			runtime.caffeineWatcher:start()
		end
	end
	if hs.screen and hs.screen.watcher and type(hs.screen.watcher.new) == "function" then
		runtime.screenWatcher = hs.screen.watcher.new(function()
			check_display()
		end)
		if runtime.screenWatcher and runtime.screenWatcher.start then
			runtime.screenWatcher:start()
		end
	end

	process_existing()
	refresh_status()
end

return M
