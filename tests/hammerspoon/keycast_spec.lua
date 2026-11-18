local KEYCAST_PATH = "home/dot_hammerspoon/keycast.lua"
local MODEL_PATH = "home/dot_hammerspoon/keycast_model.lua"

local function make_hs(env)
	local api = {}
	local model = assert(loadfile(MODEL_PATH))()

	local function make_timer(kind, interval, callback)
		local timer = {
			kind = kind,
			interval = interval,
			callback = callback,
			running = false,
			stop_calls = 0,
		}
		function timer:start()
			self.running = true
			return self
		end
		function timer:stop()
			self.running = false
			self.stop_calls = self.stop_calls + 1
		end
		function timer:fire()
			if self.running then
				self.callback()
			end
		end
		table.insert(kind == "delayed" and env.delayed or env.timers, timer)
		return timer
	end

	api.timer = {
		new = function(interval, callback)
			return make_timer("repeating", interval, callback)
		end,
		delayed = {
			new = function(interval, callback)
				return make_timer("delayed", interval, callback)
			end,
		},
		secondsSinceEpoch = function()
			return env.now
		end,
	}

	api.eventtap = {
		event = {
			types = { keyDown = "keyDown" },
			properties = { keyboardEventAutorepeat = "autorepeat" },
		},
		isSecureInputEnabled = function()
			return env.secure
		end,
		new = function(types, callback)
			env.tap_count = env.tap_count + 1
			local tap = {
				types = types,
				callback = callback,
				enabled = true,
				stop_calls = 0,
				enable_calls = 0,
			}
			function tap:start()
				self.enabled = true
				return self
			end
			function tap:stop()
				self.enabled = false
				self.stop_calls = self.stop_calls + 1
			end
			function tap:isEnabled()
				return self.enabled
			end
			function tap:enable()
				self.enabled = true
				self.enable_calls = self.enable_calls + 1
			end
			env.taps[#env.taps + 1] = tap
			return tap
		end,
	}

	api.keycodes = { map = { a = 0, v = 9, s = 1, escape = 53 } }
	api.canvas = {
		new = function(frame)
			env.canvas_count = env.canvas_count + 1
			local canvas = {
				current_frame = frame,
				visible = false,
				deleted = false,
				elements = {},
			}
			function canvas:level(value)
				self.canvas_level = value
				return self
			end
			function canvas:behaviorAsLabels(value)
				self.behaviors = value
				return self
			end
			function canvas:clickActivating(value)
				self.click_activating = value
				return self
			end
			function canvas:frame(value)
				if value ~= nil then
					self.current_frame = value
				end
				return self.current_frame
			end
			function canvas:replaceElements(...)
				self.elements = { ... }
			end
			function canvas:show()
				self.visible = true
			end
			function canvas:hide()
				self.visible = false
			end
			function canvas:delete()
				self.deleted = true
				self.visible = false
			end
			env.canvases[#env.canvases + 1] = canvas
			return canvas
		end,
	}

	local watcher = {
		new = function(callback)
			env.watcher_count = env.watcher_count + 1
			local object = { callback = callback, running = false, stop_calls = 0 }
			function object:start()
				self.running = true
				return self
			end
			function object:stop()
				self.running = false
				self.stop_calls = self.stop_calls + 1
			end
			function object:fire()
				if self.running then
					self.callback("frontmost", 1, env.frontmost)
				end
			end
			env.watchers[#env.watchers + 1] = object
			return object
		end,
	}

	api.application = {
		frontmostApplication = function()
			return env.frontmost
		end,
		watcher = watcher,
	}
	api.printf = function(format, ...)
		env.logs[#env.logs + 1] = string.format(format, ...)
	end
	return api, model
end

local function new_environment()
	local env = {
		now = 100,
		secure = false,
		tap_count = 0,
		canvas_count = 0,
		watcher_count = 0,
		taps = {},
		canvases = {},
		timers = {},
		delayed = {},
		watchers = {},
		logs = {},
	}
	env.frontmost = {
		bundleID = function()
			return "com.example.editor"
		end,
		name = function()
			return "Editor"
		end,
	}
	return env
end

local function event(key_code, characters, flags, repeat_value)
	return {
		getKeyCode = function()
			return key_code
		end,
		getCharacters = function()
			return characters or ""
		end,
		getFlags = function()
			return flags or {}
		end,
		getProperty = function(_, property)
			if property == "autorepeat" then
				return repeat_value and 1 or 0
			end
			return nil
		end,
	}
end

local function canvas_text(canvas)
	local result = {}
	for _, element in ipairs(canvas.elements) do
		if element.type == "text" then
			table.insert(result, element.text)
		end
	end
	return result
end

describe("keycast runtime", function()
	local prior_hs
	local prior_global_hs
	local env
	local Keycast
	local model

	local function setup()
		env = new_environment()
		local hs_api
		hs_api, model = make_hs(env)
		hs = hs_api
		_G.hs = hs_api
		_G.BobKeycast = nil
		package.loaded.keycast_model = model
		package.loaded.keycast = nil
		Keycast = assert(loadfile(KEYCAST_PATH))()
	end

	before_each(function()
		prior_hs = hs
		prior_global_hs = _G.hs
		setup()
	end)

	after_each(function()
		hs = prior_hs
		_G.hs = prior_global_hs
		_G.BobKeycast = nil
		package.loaded.keycast = nil
	end)

	local function show(overrides)
		local options = {
			session_id = "session-one",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
		}
		for key, value in pairs(overrides or {}) do
			options[key] = value
		end
		local result = Keycast.show(options)
		if not result then
			error(env.logs[#env.logs] or "keycast.show returned false")
		end
		return result
	end

	it("loads without touching hs APIs", function()
		hs = nil
		_G.hs = nil
		_G.BobKeycast = nil
		local ok, module = pcall(assert(loadfile(KEYCAST_PATH)))
		assert.is_true(ok)
		assert.is_table(module)
		hs = make_hs(env)
		_G.hs = hs
	end)

	it("keeps one tap, canvas, timer, and watcher for identical shows", function()
		assert.is_true(show())
		local canvas = env.canvases[1]
		assert.is_true(show())
		assert.equals(1, env.tap_count)
		assert.equals(1, env.canvas_count)
		assert.equals(1, #env.timers)
		assert.equals(1, env.watcher_count)
		assert.equals(canvas, env.canvases[1])
		assert.is_true(Keycast.isActive())
	end)

	it("does not start resources for off mode or a tiny region", function()
		assert.is_true(show({ mode = "off" }))
		assert.is_true(show({ mode = "all", region = { x = 0, y = 0, w = 300, h = 100 } }))
		assert.equals(0, env.tap_count)
		assert.equals(0, env.canvas_count)
		assert.equals(0, #env.timers)
		assert.equals(0, env.watcher_count)
		assert.is_false(Keycast.isActive())
	end)

	it("hide stops and releases all resources and is safe twice", function()
		show()
		local tap = env.taps[1]
		local timer = env.timers[1]
		local watcher = env.watchers[1]
		local canvas = env.canvases[1]
		tap.callback(event(0, "a"))
		local delayed = env.delayed[1]
		assert.is_truthy(delayed)
		assert.is_true(Keycast.hide())
		assert.is_true(Keycast.hide())
		assert.equals(1, tap.stop_calls)
		assert.equals(1, timer.stop_calls)
		assert.equals(1, watcher.stop_calls)
		assert.is_true(canvas.deleted)
		assert.equals(1, delayed.stop_calls)
		assert.is_false(Keycast.isActive())
		assert.same({}, _G.BobKeycast.trail)
	end)

	it("always passes key events through, including excluded chords and failures", function()
		show()
		local tap = env.taps[1]
		assert.is_false(tap.callback(event(0, "a")))
		assert.equals(1, #_G.BobKeycast.trail)
		assert.is_false(tap.callback(event(9, "v", { ctrl = true, alt = true, shift = true })))
		assert.equals(1, #_G.BobKeycast.trail)

		env.secure = true
		assert.is_false(tap.callback(event(0, "a")))
		assert.same({}, _G.BobKeycast.trail)
		assert.is_true(_G.BobKeycast.indicator)

		env.secure = false
		model.update = function()
			error("model failure")
		end
		assert.is_false(tap.callback(event(0, "a")))
		assert.is_false(Keycast.isActive())
		assert.equals(1, #env.logs)
		assert.is_false(Keycast.show({
			session_id = "session-one",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
		}))
		assert.equals(1, env.tap_count)
	end)

	it("blanks and clears the trail while secure input is enabled", function()
		show()
		local tap = env.taps[1]
		tap.callback(event(0, "a"))
		env.delayed[1]:fire()
		assert.is_true(env.canvases[1].visible)
		env.secure = true
		tap.callback(event(0, "a"))
		env.delayed[2]:fire()
		assert.same({}, _G.BobKeycast.trail)
		assert.is_true(_G.BobKeycast.indicator)
		assert.same({ "🔒 secure" }, canvas_text(env.canvases[1]))
	end)

	it("blanks and clears the trail when a denied app becomes frontmost", function()
		show()
		local tap = env.taps[1]
		tap.callback(event(0, "a"))
		env.delayed[1]:fire()
		env.frontmost = {
			bundleID = function()
				return "com.apple.keychainaccess"
			end,
			name = function()
				return "Keychain Access"
			end,
		}
		env.watchers[1]:fire()
		env.delayed[2]:fire()
		assert.same({}, _G.BobKeycast.trail)
		assert.is_true(_G.BobKeycast.indicator)
		assert.same({ "🔒 secure" }, canvas_text(env.canvases[1]))
	end)

	it("expires entries and hides the canvas without another key event", function()
		show()
		env.taps[1].callback(event(0, "a"))
		env.delayed[1]:fire()
		assert.is_true(env.canvases[1].visible)
		env.now = 103
		env.timers[1]:fire()
		assert.same({}, _G.BobKeycast.trail)
		assert.is_false(env.canvases[1].visible)
	end)

	it("uses a click-through screenSaver canvas without a mouse callback", function()
		show()
		local canvas = env.canvases[1]
		assert.equals("screenSaver", canvas.canvas_level)
		assert.same({ "canJoinAllSpaces", "fullScreenAuxiliary" }, canvas.behaviors)
		assert.is_false(canvas.click_activating)
		assert.is_nil(canvas.mouseCallback)
	end)

	it("relayouts a changed region without a new tap and resets on a new session", function()
		show()
		local tap = env.taps[1]
		local canvas = env.canvases[1]
		tap.callback(event(0, "a"))
		local frame_before = canvas.current_frame
		show({ region = { x = 30, y = 40, w = 900, h = 500 } })
		assert.equals(1, env.tap_count)
		assert.equals(1, env.canvas_count)
		assert.is_not.equals(frame_before.x, canvas.current_frame.x)
		assert.equals(1, #_G.BobKeycast.trail)

		show({ session_id = "session-two" })
		assert.same({}, _G.BobKeycast.trail)
		assert.equals(2, env.tap_count)
		assert.equals(2, env.canvas_count)
		assert.equals(1, tap.stop_calls)
	end)

	it("check re-enables a tap that was disabled", function()
		show()
		local tap = env.taps[1]
		tap.enabled = false
		assert.is_true(Keycast.check())
		assert.is_true(tap.enabled)
		assert.equals(1, tap.enable_calls)
	end)
end)

describe("keycast keystroke log", function()
	local prior_hs
	local prior_global_hs
	local env
	local Keycast

	local function setup()
		env = new_environment()
		local hs_api
		hs_api, _ = make_hs(env)
		hs = hs_api
		_G.hs = hs_api
		_G.BobKeycast = nil
		package.loaded.keycast_model = assert(loadfile(MODEL_PATH))()
		package.loaded.keycast = nil
		Keycast = assert(loadfile(KEYCAST_PATH))()
	end

	before_each(function()
		prior_hs = hs
		prior_global_hs = _G.hs
		setup()
	end)

	after_each(function()
		hs = prior_hs
		_G.hs = prior_global_hs
		_G.BobKeycast = nil
		package.loaded.keycast = nil
	end)

	local function tmp_log()
		local path = os.tmpname()
		os.remove(path)
		return path
	end

	local function read_lines(path)
		local handle = io.open(path, "r")
		if not handle then
			return {}
		end
		local lines = {}
		for line in handle:lines() do
			table.insert(lines, line)
		end
		handle:close()
		return lines
	end

	it("logs only shown entries with id and text", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-one",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		local tap = env.taps[1]
		tap.callback(event(0, "a"))
		tap.callback(event(0, "b"))
		assert.equals(2, #_G.BobKeycast.log_buffer)
		assert.is_true(_G.BobKeycast.log_buffer[1]:find('"id":1', 1, true) ~= nil)
		assert.is_true(_G.BobKeycast.log_buffer[2]:find('"id":1', 1, true) ~= nil)
		assert.is_true(_G.BobKeycast.log_buffer[2]:find('"text":"ab"', 1, true) ~= nil)
		env.timers[1]:fire()
		local lines = read_lines(log_path)
		assert.equals(2, #lines)
		os.remove(log_path)
	end)

	local function log_ids()
		local ids = {}
		for _, line in ipairs(_G.BobKeycast.log_buffer) do
			local id = line:match('"id":(%d+)')
			table.insert(ids, tonumber(id))
		end
		return ids
	end

	it("uses distinct increasing ids across expiry", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-expiry",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		local tap = env.taps[1]
		tap.callback(event(0, "c"))
		tap.callback(event(8, "i"))
		assert.same({ 1, 1 }, log_ids())
		env.now = env.now + 3
		tap.callback(event(7, "x"))
		local ids = log_ids()
		assert.equals(3, #ids)
		assert.equals(1, ids[1])
		assert.equals(1, ids[2])
		assert.equals(2, ids[3])
		assert.is_true(ids[3] > ids[1])
		os.remove(log_path)
	end)

	it("uses distinct increasing ids across a secure-input blank", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-secure",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		local tap = env.taps[1]
		tap.callback(event(0, "a"))
		assert.same({ 1 }, log_ids())
		env.secure = true
		tap.callback(event(0, "b"))
		assert.same({ 1 }, log_ids())
		env.secure = false
		tap.callback(event(0, "c"))
		assert.same({ 1, 2 }, log_ids())
		os.remove(log_path)
	end)

	it("uses distinct increasing ids across a mode change", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-mode",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		local tap = env.taps[1]
		tap.callback(event(0, "a"))
		assert.same({ 1 }, log_ids())
		assert.is_true(Keycast.show({
			session_id = "log-mode",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "chords",
			log_path = log_path,
		}))
		tap.callback(event(53, "escape"))
		assert.same({ 2 }, log_ids())
		local lines = read_lines(log_path)
		assert.equals(1, #lines)
		assert.is_true(lines[1]:find('"id":1', 1, true) ~= nil)
		os.remove(log_path)
	end)

	it("restarts ids at 1 on a new session", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-session-one",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		env.taps[1].callback(event(0, "a"))
		assert.same({ 1 }, log_ids())
		assert.is_true(Keycast.show({
			session_id = "log-session-two",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		env.taps[2].callback(event(0, "b"))
		assert.same({ 1 }, log_ids())
		local lines = read_lines(log_path)
		assert.equals(1, #lines)
		assert.is_true(lines[1]:find('"id":1', 1, true) ~= nil)
		assert.is_true(lines[1]:find('"text":"a"', 1, true) ~= nil)
		assert.is_true(Keycast.hide())
		os.remove(log_path)
	end)

	it("renders a long run as an ellipsis plus its tail", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-long",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		local tap = env.taps[1]
		for _ = 1, 40 do
			tap.callback(event(0, "a"))
		end
		env.delayed[1]:fire()
		local texts = canvas_text(env.canvases[1])
		assert.equals(1, #texts)
		local shown = texts[1]
		assert.is_true(shown:sub(1, 3) == "…")
		assert.equals("…" .. string.rep("a", 23), shown)
		assert.is_true(
			_G.BobKeycast.log_buffer[#_G.BobKeycast.log_buffer]:find('"text":"' .. string.rep("a", 40) .. '"', 1, true)
				~= nil
		)
		os.remove(log_path)
	end)

	it("logs nothing for off, secure, denied, or excluded input", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-two",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		local tap = env.taps[1]
		tap.callback(event(9, "v", { ctrl = true, alt = true, shift = true }))
		assert.equals(0, #(_G.BobKeycast.log_buffer or {}))
		env.secure = true
		tap.callback(event(0, "a"))
		assert.equals(0, #(_G.BobKeycast.log_buffer or {}))
		env.secure = false
		_G.BobKeycast.denied = true
		_G.BobKeycast.indicator = true
		tap.callback(event(0, "a"))
		assert.equals(0, #(_G.BobKeycast.log_buffer or {}))
		assert.is_true(Keycast.show({
			session_id = "log-two",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "off",
			log_path = log_path,
		}))
		assert.is_nil(_G.BobKeycast.log_path)
		os.remove(log_path)
	end)

	it("hide flushes the buffer to the log file", function()
		local log_path = tmp_log()
		assert.is_true(Keycast.show({
			session_id = "log-three",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		env.taps[1].callback(event(0, "a"))
		assert.equals(1, #_G.BobKeycast.log_buffer)
		assert.is_true(Keycast.hide())
		assert.equals(0, #_G.BobKeycast.log_buffer)
		local lines = read_lines(log_path)
		assert.equals(1, #lines)
		os.remove(log_path)
	end)

	it("a write failure leaves the overlay working", function()
		local log_path = os.tmpname()
		os.remove(log_path)
		assert.is_true(os.execute(string.format("mkdir -p %q", log_path)) == 0 or true)
		assert.is_true(Keycast.show({
			session_id = "log-four",
			region = { x = 10, y = 20, w = 800, h = 450 },
			mode = "all",
			log_path = log_path,
		}))
		env.taps[1].callback(event(0, "a"))
		env.timers[1]:fire()
		assert.is_true(Keycast.isActive())
		assert.equals(1, #_G.BobKeycast.trail)
		assert.is_nil(_G.BobKeycast.log_path)
		os.execute(string.format("rm -rf %q", log_path))
	end)
end)
