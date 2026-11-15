local PICKER_PATH = "home/dot_hammerspoon/screenshot_region.lua"
local SETTINGS_KEY = "macscrotLastRegion"
local HINT_TEXT =
	"Drag: new box · ⌘-drag: move · Corners: resize · F: full screen · W: window\nEnter: capture · ⌘Enter: capture + save default · Esc: cancel"

local function copy_rect(rect)
	return { x = rect.x, y = rect.y, w = rect.w, h = rect.h }
end

local function make_screen(env)
	local screen = {}
	function screen:frame()
		return { x = env.frame.x, y = env.frame.y, w = env.frame.w, h = env.frame.h }
	end
	return screen
end

local function make_hs(env)
	local hs = {}
	local mousePoint = env.mousePoint or { x = 200, y = 200 }
	local windows = {}
	for _, spec in ipairs(env.windows or {}) do
		local window = {}
		function window:isStandard()
			return spec.standard ~= false
		end
		function window:frame()
			return copy_rect(spec.frame)
		end
		function window:application()
			return {
				bundleID = function()
					return spec.bundleID
				end,
			}
		end
		table.insert(windows, window)
	end
	hs.window = {
		orderedWindows = function()
			return windows
		end,
	}

	hs.screen = {
		allScreens = function()
			return { make_screen(env) }
		end,
		mainScreen = function()
			return make_screen(env)
		end,
	}

	hs.mouse = {
		getCurrentScreen = function()
			return make_screen(env)
		end,
		absolutePosition = function()
			return mousePoint
		end,
	}

	hs.settings = {
		get = function(key)
			local value = env.settings[key]
			if type(value) == "table" then
				return copy_rect(value)
			end
			return value
		end,
		set = function(key, value)
			env.settingsWrites = env.settingsWrites + 1
			if type(value) == "table" then
				env.settings[key] = copy_rect(value)
			else
				env.settings[key] = value
			end
		end,
	}

	hs.canvas = {
		new = function(frame)
			local canvas = {
				frame = copy_rect(frame),
				replaceCalls = {},
				shown = false,
				broughtToFront = false,
				hidden = false,
				deleted = false,
			}
			function canvas:replaceElements(...)
				table.insert(self.replaceCalls, { ... })
			end
			function canvas:level(_level)
				return self
			end
			function canvas:behaviorAsLabels(_labels)
				return self
			end
			function canvas:clickActivating(_flag)
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
			function canvas:minimumTextSize(spec)
				local text = spec
				if type(spec) == "table" then
					text = spec.text or ""
				end
				text = tostring(text)
				local longest = 0
				local lines = 1
				for line in string.gmatch(text, "[^\n]+") do
					if #line > longest then
						longest = #line
					end
				end
				for _ in string.gmatch(text, "\n") do
					lines = lines + 1
				end
				return { w = longest * 7, h = lines * 16 }
			end
			env.canvas = canvas
			if env.canvasFails then
				return nil
			end
			return canvas
		end,
	}

	hs.eventtap = {
		event = {
			types = {
				leftMouseDown = "leftMouseDown",
				leftMouseDragged = "leftMouseDragged",
				leftMouseUp = "leftMouseUp",
				keyDown = "keyDown",
			},
		},
		new = function(_types, callback)
			local tap = { stopped = false, startCalls = 0 }
			function tap:start()
				self.startCalls = self.startCalls + 1
				return self
			end
			function tap:stop()
				self.stopped = true
			end
			env.tap = tap
			env.tapCallback = callback
			return tap
		end,
	}

	hs.keycodes = {
		map = {
			escape = 53,
			["return"] = 36,
			padenter = 76,
			m = 46,
			f = 3,
			w = 13,
			s = 1,
		},
	}

	hs.timer = {
		doAfter = function(delay, fn)
			local timer = { delay = delay, stopped = false }
			function timer:stop()
				self.stopped = true
			end
			table.insert(env.doAfterCalls, timer)
			if delay <= 1 then
				fn()
			else
				timer.callback = fn
			end
			return timer
		end,
	}

	hs.notify = {
		show = function(...)
			table.insert(env.notifications, { ... })
		end,
	}

	return hs
end

local function make_event(eventType, x, y, flags, keyCode)
	return {
		getType = function(_self)
			return eventType
		end,
		location = function(_self)
			return { x = x, y = y }
		end,
		getFlags = function(_self)
			return flags or {}
		end,
		getKeyCode = function(_self)
			return keyCode
		end,
	}
end

local function fire(env, eventType, x, y, flags, keyCode)
	local event = make_event(eventType, x, y, flags, keyCode)
	local result = env.tapCallback(event)
	assert.is_true(result)
end

local function setup(options)
	options = options or {}
	local frame = options.frame or { x = 0, y = 0, w = 1000, h = 800 }
	local saved = options.saved
	if saved == nil then
		saved = { x = 100, y = 100, w = 600, h = 400 }
	end
	local env = {
		previous_hs = _G.hs,
		frame = copy_rect(frame),
		settings = {},
		settingsWrites = 0,
		confirmed = {},
		doAfterCalls = {},
		notifications = {},
		cancelReasons = {},
		canvas = nil,
		windows = options.windows or {},
		mousePoint = options.mousePoint,
		tap = nil,
		tapCallback = nil,
		canvasFails = options.canvas_fails == true,
		handle = nil,
	}
	if saved then
		env.settings[SETTINGS_KEY] = copy_rect(saved)
	end
	if options.settings then
		for key, value in pairs(options.settings) do
			if type(value) == "table" then
				env.settings[key] = copy_rect(value)
			else
				env.settings[key] = value
			end
		end
	end
	_G.hs = make_hs(env)
	local picker = assert(loadfile(PICKER_PATH))()
	local pickOpts = options.opts
	if pickOpts then
		local copied = {}
		for key, value in pairs(pickOpts) do
			copied[key] = value
		end
		local userCancel = copied.onCancel
		copied.onCancel = function(reason)
			table.insert(env.cancelReasons, reason)
			if userCancel then
				userCancel(reason)
			end
		end
		pickOpts = copied
	end
	local function pick()
		env.handle = picker.pick(function(finalRegion)
			table.insert(env.confirmed, copy_rect(finalRegion))
		end, pickOpts)
	end
	function env.repick()
		pick()
	end
	function env.restore()
		_G.hs = env.previous_hs
	end
	pick()
	return env
end

local function event_types()
	return _G.hs.eventtap.event.types
end

local function press(env, x, y, flags)
	fire(env, event_types().leftMouseDown, x, y, flags, nil)
end

local function drag(env, x, y, flags)
	fire(env, event_types().leftMouseDragged, x, y, flags, nil)
end

local function release(env, x, y, flags)
	fire(env, event_types().leftMouseUp, x, y, flags, nil)
end

local function key(env, name, flags)
	fire(env, event_types().keyDown, 0, 0, flags or {}, _G.hs.keycodes.map[name])
end

local function latest_elements(env)
	local calls = env.canvas.replaceCalls
	assert.is_true(#calls > 0, "expected at least one render")
	return calls[#calls]
end

local function rendered_region(env)
	for _, element in ipairs(latest_elements(env)) do
		if element.action == "stroke" and element.strokeWidth == 2 then
			return {
				x = element.frame.x + env.frame.x,
				y = element.frame.y + env.frame.y,
				w = element.frame.w,
				h = element.frame.h,
			}
		end
	end
	error("stroke element not found")
end

local function hint_text(env)
	for _, element in ipairs(latest_elements(env)) do
		if
			element.type == "text"
			and type(element.text) == "string"
			and (element.text:find("\n", 1, true) or element.text == "W: no window here")
		then
			return element.text
		end
	end
	error("hint text not found")
end

local function assert_region(actual, x, y, w, h)
	assert.same({ x = x, y = y, w = w, h = h }, actual)
end

local function assert_picker_open(env)
	assert.is_false(env.tap.stopped)
	assert.is_false(env.canvas.deleted)
	assert.equals(0, #env.confirmed)
end

describe("screenshot region picker draw-first gestures", function()
	local active = nil

	after_each(function()
		if active then
			active.restore()
			active = nil
		end
	end)

	local function open(options)
		active = setup(options)
		return active
	end

	it("1. plain drag inside the box draws a new box", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 350, 280)
		release(env, 350, 280)
		key(env, "return")
		assert_region(env.confirmed[1], 200, 200, 150, 80)
		assert_region(env.settings[SETTINGS_KEY], 100, 100, 600, 400)
		assert.equals(0, env.settingsWrites)
		assert.equals(0.08, env.doAfterCalls[1].delay)
	end)

	it("2. the same drag reversed draws the same box", function()
		local env = open()
		press(env, 350, 280)
		drag(env, 200, 200)
		release(env, 200, 200)
		key(env, "return")
		assert_region(env.confirmed[1], 200, 200, 150, 80)
		assert_region(env.settings[SETTINGS_KEY], 100, 100, 600, 400)
		assert.equals(0, env.settingsWrites)
	end)

	it("3. plain drag outside the box draws a new box", function()
		local env = open()
		press(env, 750, 550)
		drag(env, 900, 700)
		release(env, 900, 700)
		key(env, "return")
		assert_region(env.confirmed[1], 750, 550, 150, 150)
	end)

	it("4. cmd-drag inside the box moves it", function()
		local env = open()
		press(env, 200, 200, { cmd = true })
		drag(env, 250, 240, { cmd = true })
		release(env, 250, 240, { cmd = true })
		key(env, "return")
		assert_region(env.confirmed[1], 150, 140, 600, 400)
	end)

	it("5. cmd-drag starting outside the box moves it", function()
		local env = open()
		press(env, 800, 700, { cmd = true })
		drag(env, 850, 740, { cmd = true })
		release(env, 850, 740, { cmd = true })
		key(env, "return")
		assert_region(env.confirmed[1], 150, 140, 600, 400)
	end)

	it("6. cmd-move clamps at the screen edge", function()
		local env = open()
		press(env, 200, 200, { cmd = true })
		drag(env, 900, 200, { cmd = true })
		release(env, 900, 200, { cmd = true })
		key(env, "return")
		assert_region(env.confirmed[1], 400, 100, 600, 400)
	end)

	it("7. cmd wins over the corner handle on a tiny box", function()
		local env = open({ saved = { x = 500, y = 340, w = 24, h = 24 } })
		press(env, 500, 340, { cmd = true })
		drag(env, 530, 360, { cmd = true })
		release(env, 530, 360, { cmd = true })
		key(env, "return")
		assert_region(env.confirmed[1], 530, 360, 24, 24)
	end)

	it("7b. plain press on the tiny box corner resizes", function()
		local env = open({ saved = { x = 500, y = 340, w = 24, h = 24 } })
		press(env, 500, 340)
		drag(env, 530, 360)
		release(env, 530, 360)
		key(env, "return")
		assert_region(env.confirmed[1], 508, 348, 16, 16)
	end)

	it("8. cmd moves from the gap between handles", function()
		local env = open({ saved = { x = 500, y = 340, w = 24, h = 24 } })
		press(env, 512, 352, { cmd = true })
		drag(env, 532, 372, { cmd = true })
		release(env, 532, 372, { cmd = true })
		key(env, "return")
		assert_region(env.confirmed[1], 520, 360, 24, 24)
	end)

	it("9. plain SE-handle resize still works", function()
		local env = open()
		press(env, 700, 500)
		drag(env, 650, 450)
		release(env, 650, 450)
		key(env, "return")
		assert_region(env.confirmed[1], 100, 100, 550, 350)
	end)

	it("10. the handle hit zone is +-6 pt", function()
		local env = open()
		press(env, 104, 104)
		drag(env, 150, 160)
		release(env, 150, 160)
		key(env, "return")
		assert_region(env.confirmed[1], 150, 160, 550, 340)
	end)

	it("10b. just outside the hit zone draws instead", function()
		local env = open()
		press(env, 108, 108)
		drag(env, 150, 160)
		release(env, 150, 160)
		key(env, "return")
		assert_region(env.confirmed[1], 108, 108, 42, 52)
	end)

	it("11. clicks with no movement leave the box unchanged", function()
		local env = open()
		press(env, 300, 300)
		release(env, 300, 300)
		assert_picker_open(env)
		assert_region(rendered_region(env), 100, 100, 600, 400)
		press(env, 900, 750)
		release(env, 900, 750)
		assert_picker_open(env)
		assert_region(env.settings[SETTINGS_KEY], 100, 100, 600, 400)
		key(env, "return")
		assert_region(env.confirmed[1], 100, 100, 600, 400)
	end)

	it("12. the old box stays until the drag passes the threshold", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 202, 201)
		assert_region(rendered_region(env), 100, 100, 600, 400)
		drag(env, 260, 250)
		assert_region(rendered_region(env), 200, 200, 60, 50)
	end)

	it("13. accidental jitter restores the old box", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 205, 206)
		release(env, 206, 206)
		assert_region(rendered_region(env), 100, 100, 600, 400)
		key(env, "return")
		assert_region(env.confirmed[1], 100, 100, 600, 400)
	end)

	it("14. a deliberate thin strip is kept", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 500, 208)
		release(env, 500, 208)
		key(env, "return")
		assert_region(env.confirmed[1], 200, 200, 300, 16)
	end)

	it("15. mouse-up applies the release point", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 300, 260)
		release(env, 350, 280)
		key(env, "return")
		assert_region(env.confirmed[1], 200, 200, 150, 80)
	end)

	it("16. the mode is locked at mouse-down when cmd changes mid-drag", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 350, 280, { cmd = true })
		release(env, 350, 280, { cmd = true })
		key(env, "return")
		assert_region(env.confirmed[1], 200, 200, 150, 80)
	end)

	it("16b. a cmd press keeps moving when cmd is released mid-drag", function()
		local env = open()
		press(env, 200, 200, { cmd = true })
		drag(env, 250, 240)
		release(env, 250, 240)
		key(env, "return")
		assert_region(env.confirmed[1], 150, 140, 600, 400)
	end)

	it("17. enter mid-drag does nothing", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 350, 280)
		key(env, "return")
		assert_picker_open(env)
		release(env, 350, 280)
		key(env, "return")
		assert_region(env.confirmed[1], 200, 200, 150, 80)
		env.repick()
		press(env, 400, 400)
		drag(env, 550, 480)
		key(env, "padenter")
		assert.equals(1, #env.confirmed)
		release(env, 550, 480)
		key(env, "padenter")
		assert_region(env.confirmed[2], 400, 400, 150, 80)
	end)

	it("18. esc cancels idle and mid-drag", function()
		local env = open()
		key(env, "escape")
		assert.equals(0, #env.confirmed)
		assert_region(env.settings[SETTINGS_KEY], 100, 100, 600, 400)
		assert.is_true(env.tap.stopped)
		assert.is_true(env.canvas.deleted)
		env.repick()
		press(env, 200, 200)
		drag(env, 350, 280)
		key(env, "escape")
		assert.equals(0, #env.confirmed)
		assert_region(env.settings[SETTINGS_KEY], 100, 100, 600, 400)
		assert.is_true(env.tap.stopped)
		assert.is_true(env.canvas.deleted)
	end)

	it("19. a press outside the screen still cancels", function()
		local env = open()
		press(env, 1200, 100)
		assert.equals(0, #env.confirmed)
		assert.is_true(env.tap.stopped)
		assert.is_true(env.canvas.deleted)
	end)

	it("20. a stray mouse-up with no press is swallowed", function()
		local env = open()
		release(env, 300, 300)
		assert_picker_open(env)
		assert_region(rendered_region(env), 100, 100, 600, 400)
		key(env, "return")
		assert_region(env.confirmed[1], 100, 100, 600, 400)
	end)

	it("21. draw clamps on a negative-origin screen", function()
		local frame = { x = -1440, y = 0, w = 1440, h = 900 }
		local env = open({ frame = frame, saved = { x = -1300, y = 100, w = 400, h = 300 } })
		press(env, -1300, 200)
		drag(env, -1600, 400)
		release(env, -1600, 400)
		key(env, "return")
		assert_region(env.confirmed[1], -1440, 200, 140, 200)
	end)

	it("21b. cmd-move clamps on a negative-origin screen", function()
		local frame = { x = -1440, y = 0, w = 1440, h = 900 }
		local env = open({ frame = frame, saved = { x = -1300, y = 100, w = 400, h = 300 } })
		press(env, -1100, 300, { cmd = true })
		drag(env, -1600, -100, { cmd = true })
		release(env, -1600, -100, { cmd = true })
		key(env, "return")
		assert_region(env.confirmed[1], -1440, 0, 400, 300)
	end)

	it("22. the hint shows selector shortcuts on a fitted background", function()
		local env = open()
		assert.equals(HINT_TEXT, hint_text(env))
		local elements = latest_elements(env)
		local hintIndex = nil
		for index, element in ipairs(elements) do
			if element.type == "text" and type(element.text) == "string" and element.text == HINT_TEXT then
				hintIndex = index
			end
		end
		assert.is_not_nil(hintIndex)
		local background = elements[hintIndex - 1]
		assert.equals("rectangle", background.type)
		assert.is_true(background.frame.w > 420)
		assert.equals(42, background.frame.h)
	end)

	it("23. Enter captures without saving", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 350, 280)
		release(env, 350, 280)
		key(env, "return")
		assert_region(env.confirmed[1], 200, 200, 150, 80)
		assert.equals(0.08, env.doAfterCalls[1].delay)
		assert.equals(0, env.settingsWrites)
		assert_region(env.settings[SETTINGS_KEY], 100, 100, 600, 400)
		env.repick()
		assert_region(rendered_region(env), 100, 100, 600, 400)
	end)

	it("24. ⌘Enter captures and saves", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 350, 280)
		release(env, 350, 280)
		key(env, "return", { cmd = true })
		assert_region(env.confirmed[1], 200, 200, 150, 80)
		assert.equals(0.08, env.doAfterCalls[1].delay)
		assert.equals(1, env.settingsWrites)
		assert_region(env.settings[SETTINGS_KEY], 200, 200, 150, 80)
		env.repick()
		assert_region(rendered_region(env), 200, 200, 150, 80)
		key(env, "return")
		assert_region(env.confirmed[2], 200, 200, 150, 80)
		assert.equals(1, env.settingsWrites)
	end)

	it("25. ⌘ with the keypad Enter also saves", function()
		local env = open()
		press(env, 300, 300)
		drag(env, 500, 450)
		release(env, 500, 450)
		key(env, "padenter", { cmd = true })
		assert_region(env.settings[SETTINGS_KEY], 300, 300, 200, 150)
	end)

	it("26. only ⌘ matters", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 350, 280)
		release(env, 350, 280)
		key(env, "return", { shift = true })
		assert_region(env.confirmed[1], 200, 200, 150, 80)
		assert.equals(0, env.settingsWrites)
		env.repick()
		press(env, 200, 200)
		drag(env, 350, 280)
		release(env, 350, 280)
		key(env, "return", { cmd = true, shift = true })
		assert_region(env.confirmed[2], 200, 200, 150, 80)
		assert_region(env.settings[SETTINGS_KEY], 200, 200, 150, 80)
		assert.equals(1, env.settingsWrites)
	end)

	it("27. ⌘Enter mid-drag does nothing", function()
		local env = open()
		press(env, 200, 200)
		drag(env, 350, 280)
		key(env, "return", { cmd = true })
		assert_picker_open(env)
		assert.equals(0, env.settingsWrites)
		release(env, 350, 280)
		key(env, "return", { cmd = true })
		assert_region(env.settings[SETTINGS_KEY], 200, 200, 150, 80)
	end)

	it("28. no saved default", function()
		local env = open({ saved = false })
		key(env, "return")
		assert_region(env.confirmed[1], 200, 160, 600, 480)
		assert.is_nil(env.settings[SETTINGS_KEY])
		assert.equals(0, env.settingsWrites)
		env.repick()
		assert_region(rendered_region(env), 200, 160, 600, 480)
		key(env, "return", { cmd = true })
		assert_region(env.settings[SETTINGS_KEY], 200, 160, 600, 480)
		assert.equals(1, env.settingsWrites)
	end)

	it("29. the saved rect equals the captured rect", function()
		local env = open()
		press(env, 200.4, 200.6)
		drag(env, 350.2, 280.7)
		release(env, 350.2, 280.7)
		key(env, "return", { cmd = true })
		assert_region(env.confirmed[1], 200, 201, 150, 80)
		assert_region(env.settings[SETTINGS_KEY], 200, 201, 150, 80)
	end)
end)

describe("picker full-screen and window shortcuts", function()
	local env
	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("F selects the whole screen", function()
		env = setup({ frame = { x = -1000, y = 0, w = 1000, h = 800 } })
		key(env, "f")
		assert_region(rendered_region(env), -1000, 0, 1000, 800)
		assert_picker_open(env)
	end)

	it("W snaps to the frontmost standard window under the pointer and clamps it", function()
		env = setup({
			frame = { x = 0, y = 0, w = 1000, h = 800 },
			mousePoint = { x = 900, y = 400 },
			windows = {
				{ frame = { x = 850, y = 250, w = 400, h = 400 } },
				{ frame = { x = 800, y = 200, w = 150, h = 300 } },
			},
		})
		key(env, "w")
		assert_region(rendered_region(env), 600, 250, 400, 400)
		assert_picker_open(env)
	end)

	it("W ignores Hammerspoon windows and briefly reports an empty pointer", function()
		env = setup({
			windows = {
				{ frame = { x = 100, y = 100, w = 400, h = 300 }, bundleID = "org.hammerspoon.Hammerspoon" },
				{ frame = { x = 100, y = 100, w = 400, h = 300 }, standard = false },
			},
		})
		key(env, "w")
		assert.equals("W: no window here", hint_text(env))
		assert.is_not_nil(env.doAfterCalls[#env.doAfterCalls].callback)
		env.doAfterCalls[#env.doAfterCalls].callback()
		assert.equals(HINT_TEXT, hint_text(env))
	end)
end)

local function stroke_color(env)
	for _, element in ipairs(latest_elements(env)) do
		if element.action == "stroke" and element.strokeWidth == 2 then
			return element.strokeColor
		end
	end
	error("stroke element not found")
end

local function handle_stroke_color(env)
	for _, element in ipairs(latest_elements(env)) do
		if element.id == "nw" then
			return element.strokeColor
		end
	end
	error("handle element not found")
end

local function badge_dot_color(env)
	for _, element in ipairs(latest_elements(env)) do
		if element.id == "badgeDot" then
			return element.fillColor
		end
	end
	error("badge dot not found")
end

local function label_text(env)
	for _, element in ipairs(latest_elements(env)) do
		if element.type == "text" and type(element.text) == "string" and not element.text:find("\n", 1, true) then
			return element.text
		end
	end
	error("label text not found")
end

local function hint_background(env)
	local elements = latest_elements(env)
	for index, element in ipairs(elements) do
		if element.type == "text" and type(element.text) == "string" and element.text:find("\n", 1, true) then
			return elements[index - 1], element
		end
		if element.type == "text" and type(element.text) == "string" and element.text ~= label_text(env) then
			return elements[index - 1], element
		end
	end
	error("hint background not found")
end

describe("screenshot region picker opts", function()
	local active = nil
	local red = { red = 0.89, green = 0.25, blue = 0.23, alpha = 1 }

	after_each(function()
		if active then
			active.restore()
			active = nil
		end
	end)

	local function open(options)
		active = setup(options)
		return active
	end

	it("accent colors the stroke, handles, and badge dot", function()
		local env = open({ opts = { accent = red } })
		assert.same(red, stroke_color(env))
		assert.same(red, handle_stroke_color(env))
		assert.same(red, badge_dot_color(env))
		assert.equals("600 x 400", label_text(env))
	end)

	it("badge prefixes the size label", function()
		local env = open({ opts = { badge = "● REC" } })
		assert.equals("● REC · 600 × 400", label_text(env))
	end)

	it("hint override sizes the pill to the text", function()
		local longHint = "Drag: new box · ⌘-drag: move · Corners: resize\n"
			.. "⏎: record · ⌘⏎: record + save default · M: mic off · Esc or ⌃⌥⇧V: cancel"
		local env = open({ opts = { hint = longHint } })
		local background, text = hint_background(env)
		assert.equals(longHint, text.text)
		local longest = 0
		for line in string.gmatch(longHint, "[^\n]+") do
			if #line > longest then
				longest = #line
			end
		end
		assert.is_true(background.frame.w > 420)
		assert.equals(longest * 7 + 16, background.frame.w)
	end)

	it("badge and hint functions re-render from ctx.state", function()
		local env = open({
			opts = {
				state = { mic = "off" },
				badge = function(state)
					return "● REC " .. state.mic
				end,
				hint = function(state)
					return "line one\nmic " .. state.mic
				end,
				onKey = function(event, ctx)
					if event:getKeyCode() == _G.hs.keycodes.map.m then
						ctx.state.mic = "on"
						ctx.redraw()
						return true
					end
				end,
			},
		})
		assert.equals("● REC off · 600 × 400", label_text(env))
		assert.equals("line one\nmic off", hint_text(env))
		key(env, "m")
		assert.equals("● REC on · 600 × 400", label_text(env))
		assert.equals("line one\nmic on", hint_text(env))
		assert_picker_open(env)
	end)

	it("fallbackSettingsKey seeds only when settingsKey is empty", function()
		local env = open({
			saved = false,
			settings = { macscrotLastRegion = { x = 100, y = 100, w = 600, h = 400 } },
			opts = {
				settingsKey = "macrecLastRegion",
				fallbackSettingsKey = "macscrotLastRegion",
			},
		})
		assert_region(rendered_region(env), 100, 100, 600, 400)
		key(env, "return", { cmd = true })
		assert_region(env.confirmed[1], 100, 100, 600, 400)
		assert_region(env.settings.macrecLastRegion, 100, 100, 600, 400)
		assert_region(env.settings.macscrotLastRegion, 100, 100, 600, 400)
		assert.equals(1, env.settingsWrites)
	end)

	it("settingsKey wins over fallback and writes stay isolated", function()
		local env = open({
			saved = false,
			settings = {
				macrecLastRegion = { x = 50, y = 60, w = 200, h = 180 },
				macscrotLastRegion = { x = 100, y = 100, w = 600, h = 400 },
			},
			opts = {
				settingsKey = "macrecLastRegion",
				fallbackSettingsKey = "macscrotLastRegion",
			},
		})
		assert_region(rendered_region(env), 50, 60, 200, 180)
		press(env, 200, 200)
		drag(env, 350, 280)
		release(env, 350, 280)
		key(env, "return", { cmd = true })
		assert_region(env.confirmed[1], 200, 200, 150, 80)
		assert_region(env.settings.macrecLastRegion, 200, 200, 150, 80)
		assert_region(env.settings.macscrotLastRegion, 100, 100, 600, 400)
	end)

	it("onKey can consume Escape before default handling", function()
		local env = open({
			opts = {
				onKey = function(_event, _ctx)
					return true
				end,
			},
		})
		key(env, "escape")
		assert_picker_open(env)
		assert.same({}, env.cancelReasons)
	end)

	it("onKey fall-through still runs Escape and Enter", function()
		local env = open({
			opts = {
				onKey = function(_event, _ctx)
					return nil
				end,
			},
		})
		key(env, "escape")
		assert.same({ "esc" }, env.cancelReasons)
		assert.equals(0, #env.confirmed)
	end)

	it("ctx.cancel fires onCancel with reason key", function()
		local env = open({
			opts = {
				onKey = function(_event, ctx)
					ctx.cancel()
					return true
				end,
			},
		})
		key(env, "m")
		assert.same({ "key" }, env.cancelReasons)
		assert.is_true(env.tap.stopped)
		assert.equals(0, #env.confirmed)
	end)

	it("ctx.confirm(false) captures without saving", function()
		local env = open({
			opts = {
				onKey = function(_event, ctx)
					ctx.confirm(false)
					return true
				end,
			},
		})
		key(env, "m")
		assert_region(env.confirmed[1], 100, 100, 600, 400)
		assert.equals(0, env.settingsWrites)
		assert.same({}, env.cancelReasons)
	end)

	it("ctx.confirm(true) captures and saves the settingsKey", function()
		local env = open({
			opts = {
				onKey = function(_event, ctx)
					ctx.confirm(true)
					return true
				end,
			},
		})
		key(env, "m")
		assert_region(env.confirmed[1], 100, 100, 600, 400)
		assert_region(env.settings[SETTINGS_KEY], 100, 100, 600, 400)
		assert.equals(1, env.settingsWrites)
	end)

	it("onCancel reason is esc", function()
		local env = open({ opts = {} })
		key(env, "escape")
		assert.same({ "esc" }, env.cancelReasons)
	end)

	it("onCancel reason is offscreen", function()
		local env = open({ opts = {} })
		press(env, 1200, 100)
		assert.same({ "offscreen" }, env.cancelReasons)
	end)

	it("onCancel reason is superseded and fires once", function()
		local env = open({ opts = {} })
		env.repick()
		assert.same({ "superseded" }, env.cancelReasons)
		key(env, "escape")
		assert.same({ "superseded", "esc" }, env.cancelReasons)
	end)

	it("handle.cancel uses reason key and does not double-fire", function()
		local env = open({ opts = {} })
		env.handle.cancel()
		assert.same({ "key" }, env.cancelReasons)
		env.handle.cancel()
		assert.same({ "key" }, env.cancelReasons)
	end)

	it("captureDelay override is used on confirm", function()
		local env = open({ opts = { captureDelay = 0.15 } })
		key(env, "return")
		assert.equals(0.15, env.doAfterCalls[1].delay)
		assert_region(env.confirmed[1], 100, 100, 600, 400)
	end)

	it("failureTitle is used when the canvas cannot be created", function()
		local env = open({
			canvas_fails = true,
			opts = { failureTitle = "Recording selector failed" },
		})
		assert.same({
			{ "Recording selector failed", "", "Could not create screenshot selector" },
		}, env.notifications)
		assert.equals(0, #env.confirmed)
	end)

	it("defaults stay identical when opts is omitted", function()
		local env = open()
		assert.equals(HINT_TEXT, hint_text(env))
		assert.equals("600 x 400", label_text(env))
		local background = hint_background(env)
		assert.is_true(background.frame.w > 420)
		assert.equals(42, background.frame.h)
		assert.same({ red = 0.04, green = 0.52, blue = 1, alpha = 1 }, stroke_color(env))
		key(env, "return")
		assert.equals(0.08, env.doAfterCalls[1].delay)
		assert.equals(0, env.settingsWrites)
		assert.same({}, env.cancelReasons)
	end)
end)
