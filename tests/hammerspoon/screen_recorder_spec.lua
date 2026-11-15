local RECORDER_PATH = "home/dot_hammerspoon/screen_recorder.lua"

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

	hs.screen = {
		mainScreen = function()
			return {
				frame = function()
					return {
						x = env.frame.x,
						y = env.frame.y,
						w = env.frame.w,
						h = env.frame.h,
					}
				end,
			}
		end,
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

	hs.notify = {
		show = function(title, subtitle, info)
			table.insert(env.notifications, {
				title = title,
				subtitle = subtitle,
				info = info,
			})
		end,
	}

	hs.caffeinate = {
		sessionProperties = function()
			if env.session_throw then
				error(env.session_throw)
			end
			return env.session_properties
		end,
	}

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
		tmp = tmp_base,
		now = options.now or 1e9,
		frame = options.frame or { x = 0, y = 0, w = 1440, h = 900 },
		session_properties = options.session_properties or {},
		session_throw = options.session_throw,
		json_decode_error = options.json_decode_error,
		mtimes = {},
		mkdir_calls = {},
		fs_attribute_calls = {},
		tasks = {},
		timers = {},
		path_watchers = {},
		canvases = {},
		notifications = {},
		json_decode_calls = {},
		printf_calls = {},
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
		os.execute(string.format("rm -rf %q", env.tmp))
	end

	_G.hs = make_hs(env)
	_G.BobScreenRecorder = nil
	package.loaded.screen_recorder = nil
	local recorder = assert(loadfile(RECORDER_PATH))()
	return env, recorder
end

local function start_recorder(env, recorder)
	recorder.start({
		home = env.tmp,
		doctor_path = env.tmp .. "/bin/macrec_doctor",
		now = env.now_fn,
	})
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
	end)

	it("creates the inbox, watches it, and is idempotent on restart", function()
		env, recorder = setup()
		start_recorder(env, recorder)

		assert.equals(1, #env.path_watchers)
		assert.equals(env.requests_dir(), env.path_watchers[1].path)
		assert.is_true(env.path_watchers[1].started)
		assert.equals("dir", path_kind(env.requests_dir()))
		assert.equals("dir", path_kind(env.doctor_dir()))

		local first_watcher = env.path_watchers[1]
		start_recorder(env, recorder)
		assert.equals(1, first_watcher.stop_calls)
		assert.equals(2, #env.path_watchers)
		assert.is_true(env.path_watchers[2].started)
		assert.not_equals(first_watcher, env.path_watchers[2])
	end)

	it("processes a fresh request at start, deletes it, and launches run with argv and env", function()
		env, recorder = setup()
		env.write_request("abc", '{"action":"doctor","id":"abc","probes":["env","capture"]}', env.now)
		start_recorder(env, recorder)

		assert.is_nil((io.open(env.requests_dir() .. "/doctor-abc.json", "r")))
		assert.equals(1, #env.tasks)
		local task = env.tasks[1]
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
		assert.equals(1, #env.notifications)
		assert.equals("Recording self-test running", env.notifications[1].title)
		assert.equals("≈8 s · nothing leaves this Mac", env.notifications[1].info)
		assert.equals(1, #env.timers)
		assert.equals(1, env.timers[1].interval)
		assert.is_true(env.timers[1].started)
	end)

	it("refuses a stale request present at start", function()
		env, recorder = setup()
		env.write_request("old", '{"action":"doctor","id":"old","probes":["env"]}', env.now - 200)
		start_recorder(env, recorder)
		assert.equals(0, #env.tasks)
		local result = json_decode(env.read_result("old"))
		assert.equals("invalid", result.refused)
		assert.equals("old", result.id)
	end)

	it("refuses locked sessions without launching a task", function()
		env, recorder = setup({ session_properties = { CGSSessionScreenIsLocked = true } })
		start_recorder(env, recorder)
		env.write_request("lock1", '{"action":"doctor","id":"lock1","probes":["env"]}', env.now)
		env.path_watchers[1].callback({ env.requests_dir() .. "/doctor-lock1.json" })
		assert.equals(0, #env.tasks)
		assert.equals("locked", json_decode(env.read_result("lock1")).refused)
	end)

	it("refuses a second request while a run is in flight", function()
		env, recorder = setup()
		env.write_request("one", '{"action":"doctor","id":"one","probes":["env"]}', env.now)
		start_recorder(env, recorder)
		assert.equals(1, #env.tasks)
		env.write_request("two", '{"action":"doctor","id":"two","probes":["env"]}', env.now)
		env.path_watchers[1].callback({ env.requests_dir() .. "/doctor-two.json" })
		assert.equals(1, #env.tasks)
		assert.equals("busy", json_decode(env.read_result("two")).refused)
	end)

	it("removes the card when the doctor task exits", function()
		env, recorder = setup()
		env.write_request("done1", '{"action":"doctor","id":"done1","probes":["env"]}', env.now)
		start_recorder(env, recorder)
		local canvas = env.canvases[1]
		local timer = env.timers[1]
		env.tasks[1]:complete(0, "{}", "")
		assert.is_true(canvas.hidden)
		assert.is_true(canvas.deleted)
		assert.equals(1, timer.stop_calls)
		assert.is_false(_G.BobScreenRecorder.busy)
	end)

	it("tears down the previous task and card on restart", function()
		env, recorder = setup()
		env.write_request("live", '{"action":"doctor","id":"live","probes":["capture"]}', env.now)
		start_recorder(env, recorder)
		local task = env.tasks[1]
		local canvas = env.canvases[1]
		local timer = env.timers[1]
		local watcher = env.path_watchers[1]
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
		env.path_watchers[1].callback({ env.requests_dir() .. "/doctor-badjson.json" })
		assert.equals(0, #env.tasks)
		assert.equals("invalid", json_decode(env.read_result("badjson")).refused)
	end)
end)
