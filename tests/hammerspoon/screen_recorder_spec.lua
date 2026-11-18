local RECORDER_PATH = "home/dot_hammerspoon/screen_recorder.lua"
local MODEL_PATH = "home/dot_hammerspoon/screen_recording_model.lua"

local function json_decode(text)
	local source = tostring(text or "")
	local index = 1

	local function peek()
		return source:sub(index, index)
	end

	local function skip()
		while source:sub(index, index):match("%s") do
			index = index + 1
		end
	end

	local parse_value
	local function parse_string()
		index = index + 1
		local chars = {}
		while true do
			local char = source:sub(index, index)
			if char == "" then
				error("unterminated string")
			end
			if char == '"' then
				index = index + 1
				break
			end
			if char == "\\" then
				local escaped = source:sub(index + 1, index + 1)
				local mapped = ({
					n = "\n",
					t = "\t",
					r = "\r",
					['"'] = '"',
					["\\"] = "\\",
					["/"] = "/",
				})[escaped]
				table.insert(chars, mapped or escaped)
				index = index + 2
			else
				table.insert(chars, char)
				index = index + 1
			end
		end
		return table.concat(chars)
	end

	local function parse_number()
		local start = index
		if peek() == "-" then
			index = index + 1
		end
		while source:sub(index, index):match("%d") do
			index = index + 1
		end
		if peek() == "." then
			index = index + 1
			while source:sub(index, index):match("%d") do
				index = index + 1
			end
		end
		return tonumber(source:sub(start, index - 1))
	end

	local function parse_array()
		index = index + 1
		skip()
		local array = {}
		if peek() == "]" then
			index = index + 1
			return array
		end
		while true do
			table.insert(array, parse_value())
			skip()
			if peek() == "]" then
				index = index + 1
				break
			end
			if peek() ~= "," then
				error("expected comma")
			end
			index = index + 1
			skip()
		end
		return array
	end

	local function parse_object()
		index = index + 1
		skip()
		local object = {}
		if peek() == "}" then
			index = index + 1
			return object
		end
		while true do
			skip()
			if peek() ~= '"' then
				error("expected key")
			end
			local key = parse_string()
			skip()
			if peek() ~= ":" then
				error("expected colon")
			end
			index = index + 1
			object[key] = parse_value()
			skip()
			if peek() == "}" then
				index = index + 1
				break
			end
			if peek() ~= "," then
				error("expected comma")
			end
			index = index + 1
		end
		return object
	end

	parse_value = function()
		skip()
		local char = peek()
		if char == '"' then
			return parse_string()
		end
		if char == "{" then
			return parse_object()
		end
		if char == "[" then
			return parse_array()
		end
		if source:sub(index, index + 3) == "true" then
			index = index + 4
			return true
		end
		if source:sub(index, index + 4) == "false" then
			index = index + 5
			return false
		end
		if source:sub(index, index + 3) == "null" then
			index = index + 4
			return nil
		end
		if char == "-" or char:match("%d") then
			return parse_number()
		end
		error("unexpected json at " .. tostring(char))
	end

	return parse_value()
end

local function path_kind(path)
	local handle =
		io.popen(string.format("if [ -d %q ]; then echo dir; elif [ -e %q ]; then echo file; fi", path, path))
	local kind = handle:read("*l")
	handle:close()
	return kind
end

local function make_hs(env)
	local hs = {}

	local function make_screen()
		return {
			frame = function()
				return {
					x = env.frame.x,
					y = env.frame.y,
					w = env.frame.w,
					h = env.frame.h,
				}
			end,
			id = function()
				return env.screen_id or 1
			end,
			name = function()
				return env.screen_name or "Built-in Retina Display"
			end,
		}
	end

	hs.screen = {
		mainScreen = function()
			return make_screen()
		end,
		allScreens = function()
			return { make_screen() }
		end,
		watcher = {
			new = function(callback)
				local watcher = {
					callback = callback,
					started = false,
					stop_calls = 0,
				}
				function watcher:start()
					self.started = true
					return self
				end
				function watcher:stop()
					self.started = false
					self.stop_calls = self.stop_calls + 1
				end
				table.insert(env.screen_watchers, watcher)
				return watcher
			end,
		},
	}

	hs.fs = {
		attributes = function(path)
			table.insert(env.fs_attribute_calls, path)
			local kind = path_kind(path)
			if kind == "dir" then
				return { mode = "directory", modification = env.mtimes[path] or env.now }
			end
			if kind == "file" then
				return { mode = "file", modification = env.mtimes[path] or env.now }
			end
			return nil
		end,
		mkdir = function(path)
			table.insert(env.mkdir_calls, path)
			os.execute(string.format("mkdir -p %q", path))
			return true
		end,
		dir = function(path)
			local handle = io.popen(string.format("ls -A %q 2>/dev/null", path))
			local files = {}
			if handle then
				for line in handle:lines() do
					table.insert(files, line)
				end
				handle:close()
			end
			local i = 0
			return function()
				i = i + 1
				return files[i]
			end
		end,
	}

	hs.task = {
		new = function(command, callback, args)
			if command == "/usr/bin/osascript" and env.options.notification_create_error then
				error(env.options.notification_create_error)
			end
			if command == "/usr/bin/osascript" and env.options.notification_create_nil then
				return nil
			end
			local task = {
				command = command,
				callback = callback,
				args = args,
				started = false,
				terminated = false,
				running = false,
				environment = nil,
			}
			function task:start()
				self.started = true
				self.running = true
				self.start_calls = (self.start_calls or 0) + 1
				if self.command == "/usr/bin/osascript" and env.options.notification_start_fail then
					self.running = false
					return false
				end
				return self
			end
			function task:terminate()
				self.terminated = true
				self.running = false
			end
			function task:isRunning()
				return self.running and not self.terminated
			end
			function task:setEnvironment(environment)
				self.environment = environment
				return self
			end
			function task:complete(exit_code, stdout, stderr)
				self.running = false
				self.completed = true
				if self.callback then
					self.callback(exit_code, stdout, stderr)
				end
			end
			table.insert(env.tasks, task)
			return task
		end,
	}

	hs.timer = {
		new = function(interval, callback, continue_on_error)
			local timer = {
				interval = interval,
				callback = callback,
				continue_on_error = continue_on_error,
				started = false,
				stop_calls = 0,
			}
			function timer:start()
				self.started = true
				return self
			end
			function timer:stop()
				self.started = false
				self.stop_calls = self.stop_calls + 1
			end
			table.insert(env.timers, timer)
			return timer
		end,
		doAfter = function(delay, callback)
			local timer = {
				delay = delay,
				callback = callback,
				started = true,
				stop_calls = 0,
			}
			function timer:stop()
				self.started = false
				self.stop_calls = self.stop_calls + 1
			end
			table.insert(env.do_after, timer)
			return timer
		end,
		delayed = {
			new = function(delay, callback)
				local timer = {
					delay = delay,
					fn = callback,
					started = false,
					stop_calls = 0,
				}
				function timer:start()
					self.started = true
					return self
				end
				function timer:stop()
					self.started = false
					self.stop_calls = self.stop_calls + 1
					return self
				end
				table.insert(env.delayed_timers, timer)
				return timer
			end,
		},
		secondsSinceEpoch = function()
			return env.now
		end,
	}

	hs.pathwatcher = {
		new = function(path, callback)
			local watcher = {
				path = path,
				callback = callback,
				started = false,
				stop_calls = 0,
			}
			function watcher:start()
				self.started = true
				return self
			end
			function watcher:stop()
				self.started = false
				self.stop_calls = self.stop_calls + 1
			end
			table.insert(env.path_watchers, watcher)
			return watcher
		end,
	}

	hs.canvas = {
		new = function(frame)
			local canvas = {
				frame = {
					x = frame.x,
					y = frame.y,
					w = frame.w,
					h = frame.h,
				},
				replaceCalls = {},
				shown = false,
				broughtToFront = false,
				hidden = false,
				deleted = false,
				levelValue = nil,
				behaviors = nil,
				clickActivatingValue = nil,
			}
			function canvas:replaceElements(...)
				table.insert(self.replaceCalls, { ... })
				return self
			end
			function canvas:level(level)
				self.levelValue = level
				return self
			end
			function canvas:behaviorAsLabels(labels)
				self.behaviors = labels
				return self
			end
			function canvas:clickActivating(flag)
				self.clickActivatingValue = flag
				return self
			end
			function canvas:show()
				self.shown = true
				return self
			end
			function canvas:bringToFront(_flag)
				self.broughtToFront = true
				return self
			end
			function canvas:hide(_duration)
				self.hidden = true
			end
			function canvas:delete()
				self.deleted = true
			end
			table.insert(env.canvases, canvas)
			return canvas
		end,
	}

	hs.caffeinate = {
		sessionProperties = function()
			if env.session_throw then
				error(env.session_throw)
			end
			return env.session_properties
		end,
		watcher = {
			systemWillSleep = 1,
			screensDidLock = 2,
			systemWillPowerOff = 3,
			systemDidWake = 4,
			screensDidWake = 5,
			screensDidUnlock = 6,
			new = function(callback)
				local watcher = {
					callback = callback,
					started = false,
					stop_calls = 0,
				}
				function watcher:start()
					self.started = true
					return self
				end
				function watcher:stop()
					self.started = false
					self.stop_calls = self.stop_calls + 1
				end
				table.insert(env.caffeine_watchers, watcher)
				return watcher
			end,
		},
	}

	hs.menubar = {
		new = function(in_menu_bar, autosave_name)
			local menu = {
				in_menu_bar = in_menu_bar,
				autosave_name = autosave_name,
				title = nil,
				menu_builder = nil,
				removed = true,
				returned = false,
			}
			function menu:setTitle(title)
				self.title = title
				table.insert(env.menu_titles, title)
				return self
			end
			function menu:setMenu(builder)
				self.menu_builder = builder
				return self
			end
			function menu:removeFromMenuBar()
				self.removed = true
				self.returned = false
				return self
			end
			function menu:returnToMenuBar()
				self.returned = true
				self.removed = false
				return self
			end
			table.insert(env.menus, menu)
			return menu
		end,
	}

	hs.pasteboard = {
		changeCount = function()
			return env.pasteboard_count
		end,
		setContents = function(value)
			env.pasteboard_value = value
			table.insert(env.pasteboard_writes, value)
		end,
	}

	hs.dialog = {
		blockAlert = function(message, informative, button1, button2)
			table.insert(env.alerts, {
				message = message,
				informative = informative,
				button1 = button1,
				button2 = button2,
			})
			return env.alert_result or button2
		end,
	}

	hs.image = {
		imageFromPath = function(path)
			table.insert(env.images, path)
			return { path = path }
		end,
	}

	local styled_mt = {
		__concat = function(a, b)
			local a_text = type(a) == "table" and a.text or tostring(a)
			local b_text = type(b) == "table" and b.text or tostring(b)
			local composed = { text = a_text .. b_text, is_styledtext = true }
			setmetatable(composed, styled_mt)
			return composed
		end,
	}
	hs.styledtext = {
		defaultFonts = { menuBar = { name = ".AppleSystemUIFont", size = 13 } },
		validFont = function()
			return true
		end,
		new = function(text, attributes)
			local object = {
				text = text,
				attributes = attributes,
				is_styledtext = true,
			}
			setmetatable(object, styled_mt)
			return object
		end,
	}

	hs.keycodes = {
		map = {
			escape = 53,
			["return"] = 36,
			v = 9,
			m = 46,
		},
	}

	function hs.execute(command)
		table.insert(env.execute_calls, command)
		if tostring(command):find("reduceMotion", 1, true) then
			return env.reduce_motion and "1\n" or "0\n"
		end
		return ""
	end

	hs.json = {
		decode = function(text)
			table.insert(env.json_decode_calls, text)
			if env.json_decode_error then
				error(env.json_decode_error)
			end
			return json_decode(text)
		end,
	}

	function hs.printf(...)
		table.insert(env.printf_calls, { ... })
	end

	return hs
end

local function setup(options)
	options = options or {}
	local tmp_base = os.tmpname()
	os.remove(tmp_base)
	os.execute(string.format("mkdir -p %q", tmp_base))
	local env = {
		previous_hs = _G.hs,
		previous_runtime = _G.BobScreenRecorder,
		previous_model = package.loaded.screen_recording_model,
		previous_picker = package.loaded.screenshot_region,
		previous_mac_notify = package.loaded.mac_notify,
		options = options,
		tmp = tmp_base,
		now = options.now or 1e9,
		frame = options.frame or { x = 0, y = 0, w = 1440, h = 900 },
		session_properties = options.session_properties or {},
		session_throw = options.session_throw,
		json_decode_error = options.json_decode_error,
		pasteboard_count = options.pasteboard_count or 10,
		reduce_motion = options.reduce_motion,
		alert_result = options.alert_result,
		mtimes = {},
		mkdir_calls = {},
		fs_attribute_calls = {},
		tasks = {},
		timers = {},
		do_after = {},
		delayed_timers = {},
		path_watchers = {},
		canvases = {},
		json_decode_calls = {},
		printf_calls = {},
		menus = {},
		menu_titles = {},
		pasteboard_writes = {},
		alerts = {},
		images = {},
		execute_calls = {},
		screen_watchers = {},
		caffeine_watchers = {},
		picks = {},
	}

	function env.now_fn()
		return env.now
	end

	function env.requests_dir()
		return env.tmp .. "/tmp/screencasts/.macrec/requests"
	end

	function env.doctor_dir()
		return env.tmp .. "/tmp/screencasts/.macrec/doctor"
	end

	function env.write_request(id, body, mtime)
		os.execute(string.format("mkdir -p %q", env.requests_dir()))
		local path = env.requests_dir() .. "/doctor-" .. id .. ".json"
		local handle = assert(io.open(path, "w"))
		handle:write(body)
		handle:close()
		env.mtimes[path] = mtime or env.now
		return path
	end

	function env.read_result(id)
		local handle = io.open(env.doctor_dir() .. "/" .. id .. ".json", "r")
		if not handle then
			return nil
		end
		local text = handle:read("*a")
		handle:close()
		return text
	end

	function env.restore()
		_G.hs = env.previous_hs
		_G.BobScreenRecorder = env.previous_runtime
		package.loaded.screen_recorder = nil
		package.loaded.screen_recording_model = env.previous_model
		package.loaded.screenshot_region = env.previous_picker
		package.loaded.mac_notify = env.previous_mac_notify
		os.execute(string.format("rm -rf %q", env.tmp))
	end

	_G.hs = make_hs(env)
	_G.BobScreenRecorder = nil
	package.loaded.screen_recorder = nil
	package.loaded.screen_recording_model = assert(loadfile(MODEL_PATH))()
	package.loaded.screenshot_region = {
		pick = function(onConfirm, opts)
			local pick = {
				onConfirm = onConfirm,
				opts = opts,
				cancelled = false,
			}
			function pick.cancel()
				pick.cancelled = true
				if opts and type(opts.onCancel) == "function" then
					opts.onCancel("key")
				end
			end
			table.insert(env.picks, pick)
			return pick
		end,
	}
	package.loaded.mac_notify = nil
	local recorder = assert(loadfile(RECORDER_PATH))()
	return env, recorder
end

local function start_recorder(env, recorder)
	recorder.start({
		home = env.tmp,
		doctor_path = env.tmp .. "/bin/macrec_doctor",
		macrec_path = env.tmp .. "/bin/macrec",
		now = env.now_fn,
	})
end

local function doctor_tasks(env)
	local tasks = {}
	for _, task in ipairs(env.tasks) do
		if tostring(task.command):find("macrec_doctor", 1, true) then
			table.insert(tasks, task)
		end
	end
	return tasks
end

local function macrec_tasks(env)
	local tasks = {}
	for _, task in ipairs(env.tasks) do
		if tostring(task.command):match("macrec$") then
			table.insert(tasks, task)
		end
	end
	return tasks
end

local function tasks_with_arg(env, arg)
	local tasks = {}
	for _, task in ipairs(env.tasks) do
		for _, value in ipairs(task.args or {}) do
			if value == arg then
				table.insert(tasks, task)
				break
			end
		end
	end
	return tasks
end

local function notification_tasks(env)
	local tasks = {}
	for _, task in ipairs(env.tasks) do
		if task.command == "/usr/bin/osascript" then
			table.insert(tasks, task)
		end
	end
	return tasks
end

local function watcher_for(env, suffix)
	local found
	for _, watcher in ipairs(env.path_watchers) do
		if type(watcher.path) == "string" and watcher.path:sub(-#suffix) == suffix then
			found = watcher
		end
	end
	return found
end

local function json_encode(value)
	local value_type = type(value)
	if value == nil then
		return "null"
	end
	if value_type == "boolean" then
		return value and "true" or "false"
	end
	if value_type == "number" then
		return tostring(value)
	end
	if value_type == "string" then
		return '"' .. value:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
	end
	if value_type ~= "table" then
		error("cannot encode " .. value_type)
	end
	if #value > 0 then
		local parts = {}
		for index, item in ipairs(value) do
			parts[index] = json_encode(item)
		end
		return "[" .. table.concat(parts, ",") .. "]"
	end
	local parts = {}
	for key, item in pairs(value) do
		table.insert(parts, json_encode(tostring(key)) .. ":" .. json_encode(item))
	end
	table.sort(parts)
	return "{" .. table.concat(parts, ",") .. "}"
end

local REGION = { x = 100, y = 80, w = 640, h = 360 }

local function session_fields(overrides)
	local session = {
		schema = 1,
		id = "sess1",
		name = "20261115_142233",
		status = "done",
		region = { x = REGION.x, y = REGION.y, w = REGION.w, h = REGION.h },
		mic = false,
		probe = false,
		started_at = 1000,
		cap_seconds = 600,
		orphaned = false,
		log = "/tmp/screencasts/.macrec/sessions/sess1/log",
		acked = { notified = false, adopted = false },
		duration_s = 42,
		bytes = 4800000,
		mp4 = "/tmp/screencasts/20261115_142233.mp4",
		poster = "/tmp/screencasts/.macrec/sessions/sess1/poster.jpg",
		hosts = { apollo = "ok", athena = "ok" },
		stop_reason = "chord",
	}
	for key, value in pairs(overrides or {}) do
		session[key] = value
	end
	return session
end

local function active_fields(overrides)
	local active = {
		id = "sess1",
		name = "20261115_142233",
		state = "recording",
		region = { x = REGION.x, y = REGION.y, w = REGION.w, h = REGION.h },
		mic = false,
		probe = false,
		started_at = 1000,
		cap_seconds = 600,
		recorder_alive = true,
	}
	for key, value in pairs(overrides or {}) do
		active[key] = value
	end
	return active
end

local function status_json(overrides)
	local status = {
		schema = 1,
		active = nil,
		sessions = {},
	}
	for key, value in pairs(overrides or {}) do
		status[key] = value
	end
	return json_encode(status)
end

local function pending_task(env, arg)
	local found
	for _, task in ipairs(tasks_with_arg(env, arg)) do
		if not task.completed then
			found = task
		end
	end
	return found
end

local function complete_status(env, overrides)
	local task = pending_task(env, "--json")
	if not task then
		local debounce = env.delayed_timers[#env.delayed_timers]
		assert.is_not_nil(debounce)
		debounce.fn()
		task = pending_task(env, "--json")
	end
	assert.is_not_nil(task)
	task:complete(0, status_json(overrides), "")
end

local function complete_start(env, overrides)
	local tasks = tasks_with_arg(env, "start")
	assert.is_true(#tasks >= 1)
	local payload = {
		id = "sess1",
		name = "20261115_142233",
		started_at = env.now,
	}
	for key, value in pairs(overrides or {}) do
		payload[key] = value
	end
	tasks[#tasks]:complete(0, json_encode(payload), "")
end

local function title_text(title)
	if type(title) == "string" then
		return title
	end
	if type(title) == "table" and type(title.text) == "string" then
		return title.text
	end
	return tostring(title)
end

local function menu_items(env)
	local menu = env.menus[#env.menus]
	if not menu or type(menu.menu_builder) ~= "function" then
		return {}
	end
	return menu.menu_builder()
end

local function make_key_event(chars, mods, key_code, is_repeat)
	return {
		getCharacters = function()
			return chars
		end,
		getFlags = function()
			return mods or {}
		end,
		getKeyCode = function()
			return key_code
		end,
		["repeat"] = is_repeat,
	}
end

describe("screen recorder doctor inbox", function()
	local env, recorder

	after_each(function()
		if env then
			env.restore()
			env = nil
			recorder = nil
		end
	end)

	it("computes the opaque test card inset from the main screen's bottom-right", function()
		env, recorder = setup()
		local geo = recorder.cardGeometry({ x = 0, y = 0, w = 1440, h = 900 })
		assert.same({ x = 1176, y = 726, w = 240, h = 150 }, geo)
	end)

	it("rejects malformed, stale, and unknown-probe requests", function()
		env, recorder = setup()
		local now = 1000
		assert.is_false(select(1, recorder.validateRequest(nil, now, now)))
		assert.equals(
			"invalid",
			select(2, recorder.validateRequest({ action = "record", id = "ok", probes = { "env" } }, now, now))
		)
		assert.equals(
			"invalid",
			select(2, recorder.validateRequest({ action = "doctor", id = "bad id", probes = { "env" } }, now, now))
		)
		assert.equals(
			"invalid",
			select(2, recorder.validateRequest({ action = "doctor", id = "ok", probes = { "nope" } }, now, now))
		)
		assert.equals(
			"invalid",
			select(2, recorder.validateRequest({ action = "doctor", id = "ok", probes = { "env" } }, now - 121, now))
		)
		local ok, reason, id, probes =
			recorder.validateRequest({ action = "doctor", id = "ok_1", probes = { "env", "capture" } }, now, now)
		assert.is_true(ok)
		assert.is_nil(reason)
		assert.equals("ok_1", id)
		assert.same({ "env", "capture" }, probes)
		local life_ok, life_reason, life_id, life_probes =
			recorder.validateRequest({ action = "doctor", id = "life1", probes = { "lifecycle" } }, now, now)
		assert.is_true(life_ok)
		assert.is_nil(life_reason)
		assert.equals("life1", life_id)
		assert.same({ "lifecycle" }, life_probes)
	end)

	it("creates the inbox, watches it, and is idempotent on restart", function()
		env, recorder = setup()
		start_recorder(env, recorder)

		local requests_watcher = watcher_for(env, "/requests")
		assert.is_not_nil(requests_watcher)
		assert.equals(env.requests_dir(), requests_watcher.path)
		assert.is_true(requests_watcher.started)
		assert.is_not_nil(watcher_for(env, "/.macrec"))
		assert.equals("dir", path_kind(env.requests_dir()))
		assert.equals("dir", path_kind(env.doctor_dir()))

		start_recorder(env, recorder)
		assert.equals(1, requests_watcher.stop_calls)
		local next_requests = watcher_for(env, "/requests")
		assert.is_not_nil(next_requests)
		assert.is_true(next_requests.started)
		assert.not_equals(requests_watcher, next_requests)
	end)

	it("processes a fresh request at start, deletes it, and launches run with argv and env", function()
		env, recorder = setup()
		env.write_request("abc", '{"action":"doctor","id":"abc","probes":["env","capture"]}', env.now)
		start_recorder(env, recorder)

		assert.is_nil((io.open(env.requests_dir() .. "/doctor-abc.json", "r")))
		local tasks = doctor_tasks(env)
		assert.equals(1, #tasks)
		local task = tasks[1]
		assert.equals(env.tmp .. "/bin/macrec_doctor", task.command)
		assert.same({
			"run",
			"--id",
			"abc",
			"--rect",
			"1176,726,240,150",
			"--probes",
			"env,capture",
		}, task.args)
		assert.same({
			PATH = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
			HOME = env.tmp,
		}, task.environment)
		assert.is_true(task.started)
		assert.equals(1, #env.canvases)
		assert.equals(1176, env.canvases[1].frame.x)
		assert.equals(726, env.canvases[1].frame.y)
		assert.equals(240, env.canvases[1].frame.w)
		assert.equals(150, env.canvases[1].frame.h)
		assert.equals("screenSaver", env.canvases[1].levelValue)
		assert.equals(false, env.canvases[1].clickActivatingValue)
		assert.is_true(env.canvases[1].shown)
		assert.is_true(env.canvases[1].broughtToFront)
		assert.same({ "canJoinAllSpaces", "fullScreenAuxiliary" }, env.canvases[1].behaviors)
		local elements = env.canvases[1].replaceCalls[1]
		assert.equals("macrec self-test", elements[2].text)
		assert.equals("#E3413B", elements[1].fillColor.hex)
		assert.equals(1, #notification_tasks(env))
		assert.equals("/usr/bin/osascript", notification_tasks(env)[1].command)
		assert.equals("Recording self-test running", notification_tasks(env)[1].args[3])
		assert.equals("", notification_tasks(env)[1].args[4])
		assert.equals("≈8 s · nothing leaves this Mac", notification_tasks(env)[1].args[5])
		local blink
		for _, timer in ipairs(env.timers) do
			if timer.interval == 1 then
				blink = timer
				break
			end
		end
		assert.is_not_nil(blink)
		assert.is_true(blink.started)
	end)

	it("refuses a stale request present at start", function()
		env, recorder = setup()
		env.write_request("old", '{"action":"doctor","id":"old","probes":["env"]}', env.now - 200)
		start_recorder(env, recorder)
		assert.equals(0, #doctor_tasks(env))
		local result = json_decode(env.read_result("old"))
		assert.equals("invalid", result.refused)
		assert.equals("old", result.id)
	end)

	it("refuses locked sessions without launching a task", function()
		env, recorder = setup({ session_properties = { CGSSessionScreenIsLocked = true } })
		start_recorder(env, recorder)
		env.write_request("lock1", '{"action":"doctor","id":"lock1","probes":["env"]}', env.now)
		watcher_for(env, "/requests").callback({ env.requests_dir() .. "/doctor-lock1.json" })
		assert.equals(0, #doctor_tasks(env))
		assert.equals("locked", json_decode(env.read_result("lock1")).refused)
	end)

	it("refuses a second request while a run is in flight", function()
		env, recorder = setup()
		env.write_request("one", '{"action":"doctor","id":"one","probes":["env"]}', env.now)
		start_recorder(env, recorder)
		assert.equals(1, #doctor_tasks(env))
		env.write_request("two", '{"action":"doctor","id":"two","probes":["env"]}', env.now)
		watcher_for(env, "/requests").callback({ env.requests_dir() .. "/doctor-two.json" })
		assert.equals(1, #doctor_tasks(env))
		assert.equals("busy", json_decode(env.read_result("two")).refused)
	end)

	it("removes the card when the doctor task exits", function()
		env, recorder = setup()
		env.write_request("done1", '{"action":"doctor","id":"done1","probes":["env"]}', env.now)
		start_recorder(env, recorder)
		local canvas = env.canvases[1]
		local timer = env.timers[1]
		doctor_tasks(env)[1]:complete(0, "{}", "")
		assert.is_true(canvas.hidden)
		assert.is_true(canvas.deleted)
		assert.equals(1, timer.stop_calls)
		assert.is_false(_G.BobScreenRecorder.busy)
	end)

	it("tears down the previous task and card on restart", function()
		env, recorder = setup()
		env.write_request("live", '{"action":"doctor","id":"live","probes":["capture"]}', env.now)
		start_recorder(env, recorder)
		local task = doctor_tasks(env)[1]
		local canvas = env.canvases[1]
		local timer = env.timers[1]
		local watcher = watcher_for(env, "/requests")
		start_recorder(env, recorder)
		assert.is_true(task.terminated)
		assert.is_true(canvas.deleted)
		assert.equals(1, timer.stop_calls)
		assert.equals(1, watcher.stop_calls)
	end)

	it("refuses invalid JSON via the filename id", function()
		env, recorder = setup()
		start_recorder(env, recorder)
		env.write_request("badjson", "{not-json", env.now)
		watcher_for(env, "/requests").callback({ env.requests_dir() .. "/doctor-badjson.json" })
		assert.equals(0, #doctor_tasks(env))
		assert.equals("invalid", json_decode(env.read_result("badjson")).refused)
	end)
end)

describe("screen recorder runtime", function()
	local env, recorder

	after_each(function()
		if env then
			env.restore()
			env = nil
			recorder = nil
		end
	end)

	local function boot()
		env, recorder = setup({ now = 1000, pasteboard_count = 7 })
		start_recorder(env, recorder)
		complete_status(env)
		return env, recorder
	end

	local function confirm_region(region)
		local pick = env.picks[#env.picks]
		assert.is_not_nil(pick)
		pick.onConfirm(region or REGION)
	end

	local function finish_upload(options, overrides)
		options = options or {}
		env, recorder = setup(options)
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		confirm_region()
		complete_start(env)
		env.now = env.now + 0.2
		recorder.onChord()
		tasks_with_arg(env, "stop")[1]:complete(0, "{}", "")
		if options.clipboard_changed then
			env.pasteboard_count = env.pasteboard_count + 1
		end
		local session = {
			status = "done",
			acked = { notified = false, adopted = true },
		}
		for key, value in pairs(overrides or {}) do
			session[key] = value
		end
		complete_status(env, { sessions = { session_fields(session) } })
		return notification_tasks(env)[1]
	end

	it("walks idle → selecting → starting → recording → stopping → shipping → done", function()
		boot()
		assert.equals("idle", _G.BobScreenRecorder.model.state)
		assert.equals(1, #env.menus)
		assert.is_true(env.menus[1].removed)

		recorder.onChord()
		assert.equals("selecting", _G.BobScreenRecorder.model.state)
		assert.equals(1, #env.picks)
		assert.equals("macrecLastRegion", env.picks[1].opts.settingsKey)
		assert.equals("macscrotLastRegion", env.picks[1].opts.fallbackSettingsKey)
		assert.equals(0.15, env.picks[1].opts.captureDelay)
		assert.equals("#E3413B", env.picks[1].opts.accent.hex)
		assert.equals("● REC · KEYS", env.picks[1].opts.badge({ mic = false }))
		assert.is_true(env.picks[1].opts.hint({ mic = false }):find("M: mic off", 1, true) ~= nil)
		assert.is_true(env.picks[1].opts.hint({ mic = false }):find("K: keys all", 1, true) ~= nil)

		confirm_region()
		assert.equals("starting", _G.BobScreenRecorder.model.state)
		assert.is_true(env.picks[1].cancelled)
		local start_tasks = tasks_with_arg(env, "start")
		assert.equals(1, #start_tasks)
		assert.same({
			"start",
			"100,80,640,360",
			"--keys",
			"all",
			"--max-seconds",
			"600",
		}, start_tasks[1].args)
		assert.same({
			PATH = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
			HOME = env.tmp,
		}, start_tasks[1].environment)

		complete_start(env)
		assert.equals("recording", _G.BobScreenRecorder.model.state)
		assert.is_true(#env.canvases >= 5)
		assert.is_false(env.menus[1].removed)
		assert.is_true(title_text(env.menus[1].title):find("●", 1, true) ~= nil)

		env.now = 1042
		recorder.onChord()
		assert.equals("stopping", _G.BobScreenRecorder.model.state)
		local stop_tasks = tasks_with_arg(env, "stop")
		assert.equals(1, #stop_tasks)
		assert.same({ "stop", "--reason", "chord" }, stop_tasks[1].args)

		stop_tasks[1]:complete(0, '{"id":"sess1","stopped_by":"chord"}', "")
		assert.equals("shipping", _G.BobScreenRecorder.model.state)

		complete_status(env, {
			sessions = {
				session_fields({
					status = "done",
					acked = { notified = false, adopted = true },
				}),
			},
		})
		assert.equals("done", _G.BobScreenRecorder.model.state)
		assert.equals(1, #notification_tasks(env))
		assert.equals("Recording uploaded", notification_tasks(env)[1].args[3])
		assert.is_truthy(notification_tasks(env)[1].args[5]:find("~/tmp/screencasts/20261115_142233.mp4", 1, true))
		assert.equals(1, #env.pasteboard_writes)
		assert.equals("~/tmp/screencasts/20261115_142233.mp4", env.pasteboard_writes[1])
		-- The ship fallback owns the ack until osascript exits successfully.
		assert.equals(0, #tasks_with_arg(env, "notified"))
		notification_tasks(env)[1]:complete(0, "", "")
		assert.equals(1, #tasks_with_arg(env, "notified"))
		assert.is_true(title_text(env.menus[1].title):find("✓", 1, true) ~= nil)
		local done_timer
		for _, timer in ipairs(env.do_after) do
			if timer.delay == 3 then
				done_timer = timer
			end
		end
		assert.is_not_nil(done_timer)
		done_timer.callback()
		assert.equals("idle", _G.BobScreenRecorder.model.state)
		assert.is_true(env.menus[1].removed)
	end)

	it("debounces a picker key and the hotkey firing together", function()
		boot()
		recorder.onChord()
		assert.equals("selecting", _G.BobScreenRecorder.model.state)
		local pick = env.picks[1]
		pick.opts.onKey(
			make_key_event("v", { ctrl = true, alt = true, shift = true }, 9),
			{ state = pick.opts.state, redraw = function() end }
		)
		assert.equals("selecting", _G.BobScreenRecorder.model.state)
		assert.equals(1, #env.picks)
		env.now = 1000.2
		recorder.onChord()
		assert.equals("idle", _G.BobScreenRecorder.model.state)
	end)

	it("takes a still of the exact recording selection on the screenshot chord", function()
		boot()
		recorder.onChord()
		local pick = env.picks[1]
		local captured
		recorder.captureStill = function(region)
			captured = region
		end
		local ctx = {
			state = pick.opts.state,
			region = function()
				return { x = 25, y = 35, w = 250, h = 160 }
			end,
			cancel = function()
				pick.opts.onCancel("key")
			end,
			redraw = function() end,
		}
		assert.is_true(pick.opts.onKey(make_key_event("s", { ctrl = true, alt = true, shift = true }, 1), ctx))
		assert.same({ x = 25, y = 35, w = 250, h = 160 }, captured)
		assert.equals("idle", _G.BobScreenRecorder.model.state)
	end)

	it("starts recording directly from a screenshot selection", function()
		boot()
		recorder.startRegion({ x = 25, y = 35, w = 250, h = 160 })
		assert.equals("starting", _G.BobScreenRecorder.model.state)
		assert.same(
			{ "start", "25,35,250,160", "--keys", "all", "--max-seconds", "600" },
			tasks_with_arg(env, "start")[1].args
		)
	end)

	it("discards when the chord is pressed during starting", function()
		boot()
		recorder.onChord()
		confirm_region()
		env.now = env.now + 0.2
		recorder.onChord()
		assert.equals("starting", _G.BobScreenRecorder.model.state)
		complete_start(env)
		assert.equals("stopping", _G.BobScreenRecorder.model.state)
		assert.equals(1, #tasks_with_arg(env, "discard"))
	end)

	it("notifies and returns to idle when start fails", function()
		boot()
		recorder.onChord()
		confirm_region()
		tasks_with_arg(env, "start")[1]:complete(4, "", "Screen Recording is off for Hammerspoon")
		assert.equals("idle", _G.BobScreenRecorder.model.state)
		assert.equals(1, #notification_tasks(env))
		assert.equals("Recording didn't start", notification_tasks(env)[1].args[3])
		assert.is_true(notification_tasks(env)[1].args[5]:find("Screen Recording is off", 1, true) ~= nil)
	end)

	it("discards after a confirmed dialog and keeps recording when cancelled", function()
		env, recorder = setup({ now = 1000, alert_result = "Keep Recording" })
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		confirm_region()
		complete_start(env)
		local items = menu_items(env)
		local discard
		for _, item in ipairs(items) do
			if item.title:find("Discard", 1, true) then
				discard = item
			end
		end
		assert.is_not_nil(discard)
		discard.fn()
		assert.equals("recording", _G.BobScreenRecorder.model.state)
		assert.equals(0, #tasks_with_arg(env, "discard"))

		env.alert_result = "Discard"
		discard.fn()
		assert.equals("stopping", _G.BobScreenRecorder.model.state)
		assert.equals(1, #tasks_with_arg(env, "discard"))
		assert.equals("Discard this recording?", env.alerts[#env.alerts].message)
	end)

	it("stops for the cap, sleep, and a display change", function()
		boot()
		recorder.onChord()
		confirm_region()
		complete_start(env)
		env.now = 1600
		for _, timer in ipairs(env.timers) do
			if timer.interval == 1 and timer.started and timer.callback then
				timer.callback()
			end
		end
		assert.equals("cap", _G.BobScreenRecorder.model.stopReason)
		assert.same({ "stop", "--reason", "cap" }, tasks_with_arg(env, "stop")[1].args)

		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		confirm_region()
		complete_start(env)
		env.caffeine_watchers[1].callback(hs.caffeinate.watcher.systemWillSleep)
		assert.equals("sleep", _G.BobScreenRecorder.model.stopReason)

		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		confirm_region()
		complete_start(env)
		env.frame = { x = 0, y = 0, w = 800, h = 600 }
		env.screen_watchers[1].callback()
		assert.equals("display", _G.BobScreenRecorder.model.stopReason)
	end)

	it("posts the uploaded banner through osascript and acks only after exit 0", function()
		local notification = finish_upload({ pasteboard_count = 10 })
		assert.is_not_nil(notification)
		assert.equals("/usr/bin/osascript", notification.command)
		assert.equals("Recording uploaded", notification.args[3])
		assert.equals("0:42 · 4.8 MB · Apollo + Athena", notification.args[4])
		assert.equals("~/tmp/screencasts/20261115_142233.mp4 · path copied", notification.args[5])
		assert.is_truthy(notification.args[2]:find("item 3 of argv", 1, true))
		assert.is_nil(notification.args[2]:find("Recording uploaded", 1, true))
		assert.equals(0, #tasks_with_arg(env, "notified"))
		notification:complete(0, "", "")
		assert.same({ "ack", "sess1", "notified" }, tasks_with_arg(env, "notified")[1].args)
	end)

	it("leaves notified unacked when osascript exits nonzero", function()
		local notification = finish_upload({ pasteboard_count = 10 })
		notification:complete(1, "", "notification denied")
		assert.equals(0, #tasks_with_arg(env, "notified"))
	end)

	it("leaves notified unacked when the osascript task cannot be created", function()
		local notification = finish_upload({ pasteboard_count = 10, notification_create_nil = true })
		assert.is_nil(notification)
		assert.equals(0, #tasks_with_arg(env, "notified"))
	end)

	it("leaves notified unacked and terminates a timed-out osascript task", function()
		local notification = finish_upload({ pasteboard_count = 10 })
		local timeout
		for _, timer in ipairs(env.do_after) do
			if timer.delay == 5 then
				timeout = timer
			end
		end
		assert.is_not_nil(timeout)
		timeout.callback()
		assert.is_true(notification.terminated)
		assert.equals(0, #tasks_with_arg(env, "notified"))
		notification:complete(0, "", "")
		assert.equals(0, #tasks_with_arg(env, "notified"))
	end)

	it("posts start-failure and invalid-region banners through osascript without ack", function()
		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		confirm_region()
		tasks_with_arg(env, "start")[1]:complete(4, "", "Screen Recording is off for Hammerspoon")
		assert.equals("Recording didn't start", notification_tasks(env)[1].args[3])
		assert.is_truthy(notification_tasks(env)[1].args[5]:find("Screen Recording is off", 1, true))
		assert.equals(0, #tasks_with_arg(env, "notified"))

		env.restore()
		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		env.picks[1].onConfirm({ x = 100, y = 100, w = 0, h = 30 })
		assert.equals("Recording didn't start", notification_tasks(env)[1].args[3])
		assert.equals("The selected region is invalid.", notification_tasks(env)[1].args[5])
		assert.equals(0, #tasks_with_arg(env, "notified"))
	end)

	it("keeps a changed clipboard and states that in the banner body", function()
		local notification = finish_upload({ pasteboard_count = 10, clipboard_changed = true })
		assert.equals("~/tmp/screencasts/20261115_142233.mp4 · clipboard kept", notification.args[5])
		assert.equals(0, #env.pasteboard_writes)
	end)

	it("re-adopts a live recording, a shipping session, and an orphan", function()
		env, recorder = setup({ now = 1042 })
		start_recorder(env, recorder)
		complete_status(env, { active = active_fields({ started_at = 1000 }) })
		assert.equals("recording", _G.BobScreenRecorder.model.state)
		assert.is_true(#env.canvases >= 4)
		assert.equals(1, #tasks_with_arg(env, "adopted"))
		assert.same({ "ack", "sess1", "adopted" }, tasks_with_arg(env, "adopted")[1].args)
		assert.is_true(title_text(env.menus[1].title):find("0:42", 1, true) ~= nil)

		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env, {
			sessions = {
				session_fields({
					status = "uploading",
					acked = { notified = false, adopted = true },
				}),
			},
		})
		assert.equals("shipping", _G.BobScreenRecorder.model.state)
		assert.is_true(title_text(env.menus[1].title):find("⇡", 1, true) ~= nil)

		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env, {
			sessions = {
				session_fields({
					status = "encoding",
					orphaned = true,
					acked = { notified = false, adopted = false },
				}),
			},
		})
		assert.equals(1, #tasks_with_arg(env, "recover"))
		assert.same({ "recover", "sess1" }, tasks_with_arg(env, "recover")[1].args)
	end)

	it("tears down canvases, timers, and watchers on reload", function()
		boot()
		recorder.onChord()
		confirm_region()
		complete_start(env)
		local chrome = {}
		for _, canvas in ipairs(env.canvases) do
			table.insert(chrome, canvas)
		end
		local timers = {}
		for _, timer in ipairs(env.timers) do
			table.insert(timers, timer)
		end
		local watchers = {}
		for _, watcher in ipairs(env.path_watchers) do
			table.insert(watchers, watcher)
		end
		start_recorder(env, recorder)
		for _, canvas in ipairs(chrome) do
			assert.is_true(canvas.deleted)
		end
		for _, timer in ipairs(timers) do
			assert.equals(1, timer.stop_calls)
		end
		for _, watcher in ipairs(watchers) do
			assert.equals(1, watcher.stop_calls)
		end
	end)

	it("skips breathing, blinking, and spinner under Reduce Motion", function()
		env, recorder = setup({ now = 1000, reduce_motion = true })
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		confirm_region()
		complete_start(env)
		local saw_breath = false
		for _, timer in ipairs(env.timers) do
			if timer.interval == 0.1 or timer.interval == 0.25 then
				saw_breath = true
			end
		end
		assert.is_false(saw_breath)
		assert.equals(1, #env.execute_calls)
	end)

	it("routes failed-menu actions to the matching argv", function()
		boot()
		complete_status(env, {
			sessions = {
				session_fields({
					status = "failed",
					acked = { notified = true, adopted = true },
					log = "/tmp/session.log",
					mp4 = "/tmp/clip.mp4",
				}),
			},
		})
		assert.equals("failed", _G.BobScreenRecorder.model.state)
		local items = menu_items(env)
		local by_title = {}
		for _, item in ipairs(items) do
			by_title[item.title] = item
		end
		by_title["Retry"].fn()
		assert.same({ "retry", "sess1" }, tasks_with_arg(env, "retry")[1].args)
		by_title["Reveal"].fn()
		local reveal
		for _, task in ipairs(env.tasks) do
			if task.command == "/usr/bin/open" and task.args[1] == "/tmp/clip.mp4" then
				reveal = task
			end
		end
		assert.is_not_nil(reveal)
		by_title["Show Log"].fn()
		local log
		for _, task in ipairs(env.tasks) do
			if task.command == "/usr/bin/open" and task.args[2] == "/tmp/session.log" then
				log = task
			end
		end
		assert.is_not_nil(log)
		assert.same({ "-t", "/tmp/session.log" }, log.args)
		by_title["Dismiss"].fn()
		assert.equals("idle", _G.BobScreenRecorder.model.state)
	end)

	it("toggles the mic from the selector and passes --mic to start", function()
		boot()
		recorder.onChord()
		local pick = env.picks[1]
		local redraws = 0
		pick.opts.onKey(make_key_event("m", {}, 46), {
			state = pick.opts.state,
			redraw = function()
				redraws = redraws + 1
			end,
		})
		assert.is_true(pick.opts.state.mic)
		assert.equals(1, redraws)
		assert.equals("● REC · MIC · KEYS", pick.opts.badge(pick.opts.state))
		confirm_region()
		assert.same({
			"start",
			"100,80,640,360",
			"--mic",
			"--keys",
			"all",
			"--max-seconds",
			"600",
		}, tasks_with_arg(env, "start")[1].args)
	end)

	it("keeps doctor probes out of the UI but still acknowledges their adoption", function()
		env, recorder = setup({ now = 1001 })
		start_recorder(env, recorder)
		complete_status(env, { active = active_fields({ probe = true, started_at = 1000, cap_seconds = 8 }) })
		assert.equals("idle", _G.BobScreenRecorder.model.state)
		assert.equals(0, #env.canvases)
		-- The restart-survival drill proves re-adoption through this flag.
		assert.same({ "ack", "sess1", "adopted" }, tasks_with_arg(env, "adopted")[1].args)

		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env, {
			sessions = {
				session_fields({ id = "probe-done", probe = true, hosts = {} }),
				session_fields({
					id = "probe-failed",
					probe = true,
					status = "failed",
					acked = { notified = true, adopted = true },
				}),
			},
		})
		assert.equals("idle", _G.BobScreenRecorder.model.state)
		assert.equals(0, #notification_tasks(env))
		assert.equals(0, #tasks_with_arg(env, "notified"))
	end)

	it("persists Dismiss so a failed recording does not resurface", function()
		local failed = session_fields({
			status = "failed",
			acked = { notified = true, adopted = true },
		})
		boot()
		complete_status(env, { sessions = { failed } })
		assert.equals("failed", _G.BobScreenRecorder.model.state)
		for _, item in ipairs(menu_items(env)) do
			if item.title == "Dismiss" then
				item.fn()
			end
		end
		assert.equals("idle", _G.BobScreenRecorder.model.state)
		local dismiss = tasks_with_arg(env, "dismissed")
		assert.equals(1, #dismiss)
		assert.same({ "ack", "sess1", "dismissed" }, dismiss[1].args)
		dismiss[1]:complete(0, "", "")
		complete_status(env, {
			sessions = {
				session_fields({
					status = "failed",
					acked = { notified = true, adopted = true, dismissed = true },
				}),
			},
		})
		assert.equals("idle", _G.BobScreenRecorder.model.state)

		env.restore()
		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env, {
			sessions = {
				session_fields({
					status = "failed",
					acked = { notified = true, adopted = true, dismissed = true },
				}),
			},
		})
		assert.equals("idle", _G.BobScreenRecorder.model.state)
	end)

	local function make_keycast_fake(options)
		options = options or {}
		local fake = {
			show_calls = {},
			hide_calls = 0,
			check_calls = 0,
			active = false,
			should_throw_on_show = options.throw_on_show == true,
		}
		function fake.show(item)
			if fake.should_throw_on_show then
				error("boom keycast")
			end
			local entry = { session_id = item.session_id, mode = item.mode, region = item.region }
			table.insert(fake.show_calls, entry)
			if item.mode == "off" then
				fake.active = false
			else
				fake.active = true
			end
			return true
		end
		function fake.hide()
			fake.hide_calls = fake.hide_calls + 1
			fake.active = false
			return true
		end
		function fake.check()
			fake.check_calls = fake.check_calls + 1
			return fake.active
		end
		function fake.isActive()
			return fake.active
		end
		function fake.setMode(_mode)
			return true
		end
		return fake
	end

	local function start_live_recording(with_fake)
		local fake = with_fake
		env, recorder = setup({ now = 1000, pasteboard_count = 7 })
		if fake then
			recorder._setKeycastForTests(fake)
		end
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		local pick = env.picks[#env.picks]
		assert.is_not_nil(pick)
		pick.onConfirm(REGION)
		complete_start(env)
		assert.equals("recording", _G.BobScreenRecorder.model.state)
		return fake
	end

	local function fire_interval_timers()
		for _, timer in ipairs(env.timers) do
			if timer.interval == 1 and timer.started and timer.callback then
				timer.callback()
			end
		end
	end

	it("cycles keys from the selector and passes --keys to start", function()
		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		local pick = env.picks[1]
		assert.same({ mic = false, keys = "all" }, pick.opts.state)
		assert.equals("● REC · KEYS", pick.opts.badge(pick.opts.state))
		assert.is_true(pick.opts.hint(pick.opts.state):find("K: keys all", 1, true) ~= nil)
		local redraws = 0
		local ctx = {
			state = pick.opts.state,
			redraw = function()
				redraws = redraws + 1
			end,
		}
		assert.is_true(pick.opts.onKey(make_key_event("k", {}, nil), ctx))
		assert.equals("chords", pick.opts.state.keys)
		assert.equals(1, redraws)
		assert.equals("● REC · CHORDS", pick.opts.badge(pick.opts.state))
		assert.is_true(pick.opts.hint(pick.opts.state):find("K: keys chords", 1, true) ~= nil)
		assert.is_true(pick.opts.onKey(make_key_event("K", {}, nil), ctx))
		assert.equals("off", pick.opts.state.keys)
		assert.equals("● REC", pick.opts.badge(pick.opts.state))
		assert.is_true(pick.opts.onKey(make_key_event("k", {}, nil), ctx))
		assert.equals("all", pick.opts.state.keys)
		-- Two more presses land on off for the argv check.
		pick.opts.onKey(make_key_event("k", {}, nil), ctx)
		pick.opts.onKey(make_key_event("k", {}, nil), ctx)
		assert.equals("off", pick.opts.state.keys)
		pick.onConfirm(REGION)
		assert.equals("off", _G.BobScreenRecorder.model.selection.keys)
		local args = tasks_with_arg(env, "start")[1].args
		assert.same({ "start", "100,80,640,360", "--keys", "off", "--max-seconds", "600" }, args)
	end)

	it("shows the keycast once across repeated status refreshes", function()
		local fake = make_keycast_fake()
		start_live_recording(fake)
		assert.equals(1, #fake.show_calls)
		assert.equals("all", fake.show_calls[1].mode)
		assert.equals("sess1", fake.show_calls[1].session_id)
		assert.is_true(fake.active)
		for _ = 1, 5 do
			fire_interval_timers()
			complete_status(env, { active = active_fields({ started_at = 1000 }) })
		end
		assert.equals(1, #fake.show_calls)
		assert.is_true(fake.active)
	end)

	it("hides the keycast on chord, menu, discard, cap, display, sleep, and lock stops", function()
		local function stop_with(action)
			local fake = make_keycast_fake()
			start_live_recording(fake)
			assert.is_true(fake.active)
			env.now = env.now + 0.2
			action()
			assert.is_false(fake.active)
			assert.is_true(fake.hide_calls >= 1)
			env.restore()
		end

		stop_with(function()
			recorder.onChord()
		end)

		stop_with(function()
			for _, item in ipairs(menu_items(env)) do
				if item.title:find("Stop & Upload", 1, true) then
					item.fn()
				end
			end
		end)

		stop_with(function()
			env.alert_result = "Discard"
			for _, item in ipairs(menu_items(env)) do
				if item.title:find("Discard", 1, true) then
					item.fn()
				end
			end
		end)

		stop_with(function()
			env.now = 1600
			fire_interval_timers()
		end)

		stop_with(function()
			env.frame = { x = 0, y = 0, w = 800, h = 600 }
			env.screen_watchers[#env.screen_watchers].callback()
		end)

		stop_with(function()
			env.caffeine_watchers[1].callback(hs.caffeinate.watcher.systemWillSleep)
		end)

		stop_with(function()
			env.caffeine_watchers[1].callback(hs.caffeinate.watcher.screensDidLock)
		end)
	end)

	it("hides the keycast when the recorder task finishes and on teardown", function()
		local fake = make_keycast_fake()
		start_live_recording(fake)
		env.now = env.now + 0.2
		recorder.onChord()
		assert.is_false(fake.active)
		local stops = tasks_with_arg(env, "stop")
		assert.is_true(#stops >= 1)
		stops[#stops]:complete(0, '{"id":"sess1","stopped_by":"chord"}', "")
		assert.is_false(fake.active)
		assert.is_true(fake.hide_calls >= 1)

		env.restore()
		fake = make_keycast_fake()
		start_live_recording(fake)
		assert.is_true(fake.active)
		complete_status(env)
		assert.is_false(fake.active)
		assert.is_true(fake.hide_calls >= 1)

		env.restore()
		fake = make_keycast_fake()
		start_live_recording(fake)
		assert.is_true(fake.active)
		start_recorder(env, recorder)
		assert.is_false(fake.active)
		assert.is_true(fake.hide_calls >= 1)
	end)

	it("never shows the keycast for probe-only sessions", function()
		local fake = make_keycast_fake()
		env, recorder = setup({ now = 1001 })
		recorder._setKeycastForTests(fake)
		start_recorder(env, recorder)
		complete_status(env, { active = active_fields({ probe = true, started_at = 1000, cap_seconds = 8 }) })
		assert.equals("idle", _G.BobScreenRecorder.model.state)
		assert.equals(0, #fake.show_calls)
		assert.is_false(fake.active)
	end)

	it("persists a mid-clip keys change with macrec keys", function()
		local fake = make_keycast_fake()
		start_live_recording(fake)
		assert.equals(1, #fake.show_calls)
		local target
		for _, item in ipairs(menu_items(env)) do
			if item.title == "Show Keys: All" then
				target = item
			end
		end
		assert.is_not_nil(target)
		target.fn()
		assert.equals(2, #fake.show_calls)
		assert.equals("chords", fake.show_calls[2].mode)
		local keys_tasks = tasks_with_arg(env, "keys")
		assert.equals(1, #keys_tasks)
		assert.same({ "keys", "sess1", "chords" }, keys_tasks[1].args)
	end)

	it("re-adopts with keys off without activating the overlay", function()
		local fake = make_keycast_fake()
		env, recorder = setup({ now = 1042 })
		recorder._setKeycastForTests(fake)
		start_recorder(env, recorder)
		complete_status(env, { active = active_fields({ started_at = 1000, keys = "off" }) })
		assert.equals("recording", _G.BobScreenRecorder.model.state)
		assert.equals(1, #fake.show_calls)
		assert.equals("off", fake.show_calls[1].mode)
		assert.is_false(fake.active)
	end)

	it("keeps recording when the keycast require fails", function()
		env, recorder = setup({ now = 1000 })
		start_recorder(env, recorder)
		complete_status(env)
		assert.is_not_nil(recorder._keycast())
		recorder.onChord()
		local pick = env.picks[#env.picks]
		pick.onConfirm(REGION)
		complete_start(env)
		assert.equals("recording", _G.BobScreenRecorder.model.state)
		assert.is_true(#env.canvases >= 5)
		env.now = env.now + 0.2
		recorder.onChord()
		assert.equals("stopping", _G.BobScreenRecorder.model.state)
	end)

	it("keeps recording when Keycast.show throws", function()
		local fake = make_keycast_fake({ throw_on_show = true })
		env, recorder = setup({ now = 1000 })
		recorder._setKeycastForTests(fake)
		start_recorder(env, recorder)
		complete_status(env)
		recorder.onChord()
		local pick = env.picks[#env.picks]
		pick.onConfirm(REGION)
		complete_start(env)
		assert.equals("recording", _G.BobScreenRecorder.model.state)
		assert.is_true(#env.canvases >= 5)
		env.now = env.now + 0.2
		recorder.onChord()
		assert.equals("stopping", _G.BobScreenRecorder.model.state)
	end)

	it("calls Keycast.check on the recording tick", function()
		local fake = make_keycast_fake()
		start_live_recording(fake)
		assert.equals(0, fake.check_calls)
		fire_interval_timers()
		assert.is_true(fake.check_calls >= 1)
	end)

	it("agrees with keycast_model on the three mode names", function()
		local model = assert(loadfile(MODEL_PATH))()
		local keycast_model = assert(loadfile("home/dot_hammerspoon/keycast_model.lua"))()
		assert.equals(keycast_model.DEFAULT_MODE, model.KEYS_DEFAULT)
		for _, mode in ipairs(model.KEYS_MODES) do
			assert.is_true(keycast_model.MODES[mode] == true)
		end
		local count = 0
		for _ in pairs(keycast_model.MODES) do
			count = count + 1
		end
		assert.equals(#model.KEYS_MODES, count)
	end)
end)
