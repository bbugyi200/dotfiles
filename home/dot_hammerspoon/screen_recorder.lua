-- Hammerspoon screen-recorder runtime skeleton.
--
-- This phase owns the doctor inbox: SSH agents drop probe requests under
-- ~/tmp/screencasts/.macrec/requests/, this module validates them, draws an
-- opaque test card over the probe rectangle, and launches macrec_doctor run
-- via hs.task. recorder-runtime later grows this file into the live UI.
local M = {}

M.ACCENT_HEX = "#E3413B"
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
}

if type(BobScreenRecorder) ~= "table" then
	BobScreenRecorder = {}
end

local runtime = BobScreenRecorder
local unpackArgs = table.unpack or unpack

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
	hs.notify.show("Recording self-test running", "", body)
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

function M.start(options)
	options = options or {}
	runtime.home = options.home or os.getenv("HOME") or ""
	runtime.doctorPath = options.doctor_path or (runtime.home .. "/bin/macrec_doctor")
	runtime.nowFn = options.now or os.time
	runtime.freshSeconds = options.fresh_seconds or M.FRESH_SECONDS
	runtime.macrecDir = runtime.home .. "/tmp/screencasts/.macrec"
	runtime.requestsDir = runtime.macrecDir .. "/requests"
	runtime.doctorDir = runtime.macrecDir .. "/doctor"

	stop_runtime_object("path watcher", runtime.watcher)
	stop_runtime_object("doctor task", runtime.task)
	hide_card()
	runtime.watcher = nil
	runtime.task = nil
	runtime.busy = false
	runtime.blinkTimer = nil

	ensure_directory(runtime.requestsDir)
	ensure_directory(runtime.doctorDir)
	pcall(os.execute, string.format("chmod 700 %q %q", runtime.requestsDir, runtime.doctorDir))

	local watcher = hs.pathwatcher.new(runtime.requestsDir, function(paths)
		on_path_event(paths)
	end)
	if watcher then
		watcher:start()
		runtime.watcher = watcher
	else
		log_message("path watcher could not be created")
	end

	process_existing()
end

return M
