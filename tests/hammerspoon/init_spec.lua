local INIT_PATH = "home/dot_hammerspoon/init.lua"
local COUNTDOWN_PATH = "home/dot_hammerspoon/pomodoro_countdown.lua"

local function make_started_object(kind)
	return {
		kind = kind,
		started = false,
		stop_calls = 0,
		start_calls = 0,
		start = function(self)
			self.started = true
			self.start_calls = self.start_calls + 1
			return self
		end,
		stop = function(self)
			self.started = false
			self.stop_calls = self.stop_calls + 1
		end,
	}
end

local function make_menu(env, autosave_name)
	local menu = {
		autosave_name = autosave_name,
		title = nil,
		tooltip = nil,
		menu = nil,
		removed = false,
		returned = false,
	}

	function menu:setTitle(title)
		self.title = title
		table.insert(env.menu_title_calls, { menu = self, title = title })
		return self
	end

	function menu:setTooltip(tooltip)
		self.tooltip = tooltip
		return self
	end

	function menu:setMenu(items)
		self.menu = items
		return self
	end

	function menu:removeFromMenuBar()
		self.removed = true
		return self
	end

	function menu:returnToMenuBar()
		self.returned = true
		self.removed = false
		return self
	end

	return menu
end

local function make_task(env, command, callback, args)
	local task = {
		command = command,
		callback = callback,
		args = args,
		started = false,
		terminated = false,
		start_calls = 0,
	}

	function task:start()
		self.started = true
		self.start_calls = self.start_calls + 1
		if callback and env.task_completion then
			callback(env.task_completion.exit_code, env.task_completion.stdout, env.task_completion.stderr)
		end
		return self
	end

	function task:terminate()
		self.terminated = true
	end

	table.insert(env.tasks, task)
	return task
end

local function make_styledtext(env)
	local styled_mt = {}
	styled_mt.__concat = function(a, b)
		local function parts(value)
			if type(value) == "string" then
				return value, { { text = value, attributes = nil } }
			end
			if type(value) == "table" and value.is_styledtext then
				return value.text, value.spans
			end
			error("cannot concatenate " .. type(value))
		end

		local a_text, a_spans = parts(a)
		local b_text, b_spans = parts(b)
		local new_spans = {}
		for _, span in ipairs(a_spans) do
			table.insert(new_spans, span)
		end
		for _, span in ipairs(b_spans) do
			table.insert(new_spans, span)
		end
		local composed = {
			text = a_text .. b_text,
			spans = new_spans,
			is_styledtext = true,
		}
		setmetatable(composed, styled_mt)
		table.insert(env.styled_compositions, { text = composed.text, spans = new_spans })
		return composed
	end

	return {
		defaultFonts = {
			menuBar = { name = ".AppleSystemUIFont", size = 14 },
		},
		fontTraits = {
			boldFont = "bold",
		},
		convertFont = function(font, trait)
			table.insert(env.convert_font_calls, { font = font, trait = trait })
			return {
				name = ".SFNS-Bold",
				size = font and font.size or nil,
			}
		end,
		validFont = function(name)
			env.valid_font_calls[name] = (env.valid_font_calls[name] or 0) + 1
			if env.invalid_fonts and env.invalid_fonts[name] then
				return false
			end
			return name ~= ".SFNS-Bold"
		end,
		new = function(text, attributes)
			if env.fail_styling then
				error("injected styling failure")
			end
			table.insert(env.styled_text_calls, {
				text = text,
				attributes = attributes,
			})
			local object = {
				text = text,
				attributes = attributes,
				spans = { { text = text, attributes = attributes } },
				is_styledtext = true,
			}
			setmetatable(object, styled_mt)
			return object
		end,
	}
end

local function make_hs(env)
	local hs = {}

	hs.hotkey = {
		bind = function(mods, key, message, fn)
			local binding = { mods = mods, key = key, message = message, fn = fn }
			table.insert(env.hotkeys, binding)
			return binding
		end,
	}

	hs.task = {
		new = function(command, callback, args)
			return make_task(env, command, callback, args)
		end,
	}

	hs.timer = {
		new = function(interval, callback, continue_on_error)
			local timer = make_started_object("timer")
			timer.interval = interval
			timer.callback = callback
			timer.continue_on_error = continue_on_error
			table.insert(env.timers, timer)
			return timer
		end,
	}

	hs.menubar = {
		new = function(autosave_name)
			local menu = make_menu(env, autosave_name)
			table.insert(env.menus, menu)
			return menu
		end,
	}

	hs.caffeinate = {
		watcher = {
			systemDidWake = 1,
			screensDidWake = 2,
			screensDidUnlock = 3,
			new = function(callback)
				local watcher = make_started_object("wake_watcher")
				watcher.callback = callback
				table.insert(env.wake_watchers, watcher)
				return watcher
			end,
		},
	}

	hs.pathwatcher = {
		new = function(path, callback)
			local watcher = make_started_object("path_watcher")
			watcher.path = path
			watcher.callback = callback
			table.insert(env.path_watchers, watcher)
			return watcher
		end,
	}

	hs.notify = {
		show = function(...)
			table.insert(env.notifications, { ... })
		end,
	}

	hs.styledtext = make_styledtext(env)

	hs.host = {
		interfaceStyle = function()
			env.host_calls = (env.host_calls or 0) + 1
			if env.host_error then
				error(env.host_error)
			end
			return env.interface_style
		end,
	}

	function hs.printf(...)
		table.insert(env.printf_calls, { ... })
	end

	function hs.reload()
		env.reload_calls = env.reload_calls + 1
	end

	return hs
end

local function load_real_presentation()
	local chunk = assert(loadfile(COUNTDOWN_PATH))
	return chunk()
end

local function setup_hammerspoon_init_environment(options)
	options = options or {}
	local env = {
		previous_hs = _G.hs,
		previous_runtime = _G.BobPomodoroCountdown,
		previous_pomodoro_module = package.loaded.pomodoro_countdown,
		previous_screenshot_module = package.loaded.screenshot_region,
		hotkeys = {},
		tasks = {},
		timers = {},
		menus = {},
		wake_watchers = {},
		path_watchers = {},
		notifications = {},
		printf_calls = {},
		menu_title_calls = {},
		styled_text_calls = {},
		styled_compositions = {},
		convert_font_calls = {},
		valid_font_calls = {},
		task_completion = options.task_completion,
		reload_calls = 0,
		fail_styling = false,
		host_calls = 0,
		invalid_fonts = options.invalid_fonts,
	}

	_G.hs = make_hs(env)
	_G.BobPomodoroCountdown = options.runtime
	if options.presentation ~= nil then
		package.loaded.pomodoro_countdown = { presentation = options.presentation }
	else
		package.loaded.pomodoro_countdown = load_real_presentation()
	end
	package.loaded.screenshot_region = {
		pick = function(callback)
			table.insert(env.screenshot_pick_callbacks, callback)
		end,
	}
	env.screenshot_pick_callbacks = {}

	function env.load_init()
		return dofile(INIT_PATH)
	end

	function env.restore()
		_G.hs = env.previous_hs
		_G.BobPomodoroCountdown = env.previous_runtime
		package.loaded.pomodoro_countdown = env.previous_pomodoro_module
		package.loaded.screenshot_region = env.previous_screenshot_module
	end

	return env
end

local active_env = nil

local function load_init_with(options)
	active_env = setup_hammerspoon_init_environment(options)
	local ok, error_message = xpcall(active_env.load_init, debug.traceback)
	return ok, error_message, active_env
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

local function title_spans(title)
	if type(title) == "table" and type(title.spans) == "table" then
		return title.spans
	end
	return nil
end

local function find_span_with_text(spans, needle)
	for _, span in ipairs(spans) do
		if type(span.text) == "string" and span.text:find(needle, 1, true) then
			return span
		end
	end
	return nil
end

local function freeze_clock()
	local real_time = os.time
	local real_date = os.date
	local fixed = real_time()
	local original_time = real_time
	os.time = function(table_value)
		if table_value == nil then
			return fixed
		end
		return original_time(table_value)
	end
	os.date = function(format, time_value)
		if time_value == nil then
			return real_date(format, fixed)
		end
		return real_date(format, time_value)
	end
	return function()
		os.time = real_time
		os.date = real_date
	end, fixed
end

local function freeze_clock_at(fixed)
	local real_time = os.time
	local real_date = os.date
	local original_time = real_time
	os.time = function(table_value)
		if table_value == nil then
			return fixed
		end
		return original_time(table_value)
	end
	os.date = function(format, time_value)
		if time_value == nil then
			return real_date(format, fixed)
		end
		return real_date(format, time_value)
	end
	return function()
		os.time = real_time
		os.date = real_date
	end
end

local function today_at(hour, minute)
	local day = os.date("*t")
	day.hour = hour
	day.min = minute
	day.sec = 0
	day.isdst = nil
	return os.time(day)
end

local function task_command_text(task)
	if type(task.args) == "table" then
		for _, value in ipairs(task.args) do
			if type(value) == "string" and value:find("bob pomodoro", 1, true) then
				return value
			end
		end
	end
	return ""
end

local function menu_refresh_fn(menu)
	if type(menu.menu) ~= "table" then
		return nil
	end
	for _, item in ipairs(menu.menu) do
		if type(item) == "table" and item.title == "Refresh" and type(item.fn) == "function" then
			return item.fn
		end
	end
	return nil
end

describe("Hammerspoon init", function()
	after_each(function()
		if active_env then
			active_env.restore()
			active_env = nil
		end
	end)

	it("loads in a fresh Lua state and installs Pomodoro runtime objects", function()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		assert.equals("table", type(runtime))
		assert.is_not_nil(runtime.menu)
		assert.is_not_nil(runtime.task)
		assert.is_not_nil(runtime.tickTimer)
		assert.is_not_nil(runtime.syncTimer)
		assert.is_not_nil(runtime.wakeWatcher)
		assert.is_true(runtime.tickTimer.started)
		assert.equals(0.5, runtime.tickTimer.interval)
		assert.is_true(runtime.syncTimer.started)
		assert.is_true(runtime.wakeWatcher.started)
		assert.equals(2, #env.hotkeys)
		assert.equals(1, #env.menus)
		assert.equals(2, #env.timers)
		assert.equals(1, #env.wake_watchers)
		assert.equals(1, #env.path_watchers)
	end)

	it("replaces a stale non-table Pomodoro runtime global", function()
		local ok, error_message = load_init_with({ runtime = "stale" })
		assert.is_true(ok, error_message)
		assert.equals("table", type(_G.BobPomodoroCountdown))
	end)

	it("cleans up retained Pomodoro runtime objects and reuses the menu on reload", function()
		local ok, error_message = load_init_with()
		assert.is_true(ok, error_message)

		local first_env = active_env
		local runtime = _G.BobPomodoroCountdown
		local old_menu = runtime.menu
		local old_task = runtime.task
		local old_tick_timer = runtime.tickTimer
		local old_sync_timer = runtime.syncTimer
		local old_wake_watcher = runtime.wakeWatcher

		local second_env = setup_hammerspoon_init_environment({ runtime = runtime })
		active_env = {
			restore = function()
				second_env.restore()
				first_env.restore()
			end,
		}

		ok, error_message = xpcall(second_env.load_init, debug.traceback)
		assert.is_true(ok, error_message)

		assert.equals(old_menu, runtime.menu)
		assert.is_true(old_task.terminated)
		assert.equals(1, old_tick_timer.stop_calls)
		assert.equals(1, old_sync_timer.stop_calls)
		assert.equals(1, old_wake_watcher.stop_calls)
		assert.is_not_nil(runtime.task)
		assert.not_equals(old_task, runtime.task)
		assert.is_not_nil(runtime.tickTimer)
		assert.not_equals(old_tick_timer, runtime.tickTimer)
		assert.is_not_nil(runtime.syncTimer)
		assert.not_equals(old_sync_timer, runtime.syncTimer)
		assert.is_not_nil(runtime.wakeWatcher)
		assert.not_equals(old_wake_watcher, runtime.wakeWatcher)
	end)

	it("delivers a named active payload with full context and keeps --show-stale", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		restore_clock()

		local runtime = _G.BobPomodoroCountdown
		assert.equals("DEEP WORK", runtime.state.fullTheme)
		assert.equals("10:15", runtime.state.stopTime)
		assert.equals("0950-1015", runtime.state.range)
		assert.equals("25m", runtime.state.duration)
		assert.equals(25, runtime.state.durationMinutes)
		assert.equals(9, runtime.state.startHour)
		assert.equals(50, runtime.state.startMinute)

		assert.is_true(#env.tasks >= 1)
		assert.is_true(task_command_text(env.tasks[1]):find("--show-stale", 1, true) ~= nil)

		local title = title_text(runtime.menu.title)
		assert.is_true(title:find("🍅", 1, true) ~= nil)
		assert.is_true(title:find("DEEP WORK", 1, true) ~= nil)
		assert.is_true(title:find("(25m)", 1, true) ~= nil)
		assert.is_nil(title:find("10:15", 1, true))

		assert.is_true(runtime.menu.tooltip:find("DEEP WORK (25m)", 1, true) == 1)
		assert.is_true(runtime.menu.tooltip:find("Stops at 10:15", 1, true) ~= nil)
		assert.is_true(runtime.menu.tooltip:find(runtime.state.rawOutput, 1, true) ~= nil)

		assert.equals("DEEP WORK (25m) → 10:15", runtime.menu.menu[1].title)
		assert.equals(runtime.state.rawOutput, runtime.menu.menu[2].title)
		assert.is_true(runtime.menu.menu[3].title:find("Last sync", 1, true) ~= nil)
		assert.is_not_nil(menu_refresh_fn(runtime.menu))
	end)

	it("renders the same state without the stop before the end and with it after", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = {
			rawOutput = "[<13m] 0950-1015 — DEEP WORK",
			status = "active",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "10:15",
			startHour = 9,
			startMinute = 50,
			endHour = 10,
			endMinute = 15,
			durationMinutes = 25,
			duration = "25m",
			endEpoch = fixed + 60,
			lastSyncEpoch = fixed,
		}
		runtime.tickTimer.callback()
		local running_title = title_text(env.menu_title_calls[#env.menu_title_calls].title)
		assert.is_true(running_title:find("(25m)", 1, true) ~= nil)
		assert.is_nil(running_title:find("10:15", 1, true))

		runtime.state.endEpoch = fixed - 1
		runtime.state.status = "overdue"
		runtime.state.zeroSyncRequested = true
		env.task_completion = { exit_code = 0, stdout = "[OVERDUE by 0m] 0950-1015 — DEEP WORK", stderr = "" }
		runtime.tickTimer.callback()
		restore_clock()
		local overdue_title = title_text(env.menu_title_calls[#env.menu_title_calls].title)
		assert.is_true(overdue_title:find("(25m)", 1, true) ~= nil)
		assert.is_true(overdue_title:find("→", 1, true) ~= nil)
		assert.is_true(overdue_title:find("10:15", 1, true) ~= nil)
	end)

	it("delivers a stale-overdue payload with theme, stop time, and OVERDUE status", function()
		local restore_clock = freeze_clock()
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[OVERDUE by 45m] 0900-0915 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		restore_clock()

		local runtime = _G.BobPomodoroCountdown
		assert.equals("DEEP WORK", runtime.state.fullTheme)
		assert.equals("09:15", runtime.state.stopTime)
		assert.equals("overdue", runtime.state.status)
		assert.equals("15m", runtime.state.duration)

		assert.is_true(task_command_text(env.tasks[1]):find("--show-stale", 1, true) ~= nil)

		local title = title_text(runtime.menu.title)
		assert.is_true(title:find("DEEP WORK", 1, true) ~= nil)
		assert.is_true(title:find("(15m)", 1, true) ~= nil)
		assert.is_true(title:find("09:15", 1, true) ~= nil)
		assert.is_true(title:find("OVERDUE", 1, true) ~= nil)
		assert.is_nil(title:find("OVERDUE POMODORO", 1, true))
	end)

	it("flashes only the OVERDUE badge with constant text and context styling", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = {
			rawOutput = "[OVERDUE by 15m] 0900-0915 — DEEP WORK",
			status = "overdue",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "09:15",
			endHour = 9,
			endMinute = 15,
			durationMinutes = 15,
			duration = "15m",
			endEpoch = fixed - 901,
			lastSyncEpoch = fixed,
		}
		local base_calls = #env.menu_title_calls
		runtime.tickTimer.callback()
		runtime.tickTimer.callback()
		restore_clock()

		assert.equals(base_calls + 2, #env.menu_title_calls)
		local first_title = env.menu_title_calls[base_calls + 1].title
		local second_title = env.menu_title_calls[base_calls + 2].title
		assert.equals(title_text(first_title), title_text(second_title))

		local first_spans = assert(title_spans(first_title))
		local second_spans = assert(title_spans(second_title))
		assert.equals(9, #first_spans)
		assert.equals(9, #second_spans)
		assert.equals("DEEP WORK", first_spans[1].text)
		assert.equals(" ", first_spans[2].text)
		assert.equals("(15m)", first_spans[3].text)
		assert.equals(" → ", first_spans[4].text)
		assert.equals("09:15", first_spans[5].text)
		assert.equals(" · ", first_spans[6].text)
		assert.equals("🍅", first_spans[7].text)
		assert.equals(" ", first_spans[8].text)

		local badge_text = first_spans[9].text
		assert.equals(second_spans[9].text, badge_text)
		assert.is_true(badge_text:find("OVERDUE", 1, true) ~= nil)
		assert.is_nil(badge_text:find("POMODORO", 1, true))
		assert.equals("\194\160OVERDUE\194\160", badge_text)

		for index = 1, 8 do
			assert.are.same(first_spans[index].attributes, second_spans[index].attributes)
			assert.is_nil(first_spans[index].attributes.backgroundColor)
		end
		assert.are.same({ list = "System", name = "labelColor", alpha = 1 }, first_spans[3].attributes.color)

		local first_badge = first_spans[9].attributes
		local second_badge = second_spans[9].attributes
		assert.equals(first_badge.font.name, second_badge.font.name)
		assert.equals(first_badge.font.size, second_badge.font.size)
		assert.is_false(
			first_badge.color.hex == second_badge.color.hex
				and first_badge.backgroundColor == second_badge.backgroundColor
		)
		local steady, flash = first_badge, second_badge
		if steady.backgroundColor ~= nil then
			steady, flash = second_badge, first_badge
		end
		assert.is_nil(steady.backgroundColor)
		assert.are.same({ hex = "#E3413B", alpha = 1 }, steady.color)
		assert.are.same({ hex = "#FFFFFF", alpha = 1 }, flash.color)
		assert.are.same({ hex = "#E3413B", alpha = 1 }, flash.backgroundColor)

		local context_color = { list = "System", name = "labelColor", alpha = 1 }
		assert.are.same(context_color, first_spans[1].attributes.color)
		assert.are.same(context_color, first_spans[5].attributes.color)
		assert.are.same(context_color, first_spans[7].attributes.color)
	end)

	it("does not animate countdown, recently overdue, or missing states", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local states = {
			{ status = "active", endEpoch = fixed + 300, fullTheme = "DEEP WORK", stopTime = "10:15" },
			{ status = "overdue", endEpoch = fixed - 1, fullTheme = "DEEP WORK", stopTime = "10:15" },
			{ status = "missing" },
		}
		local runtime = _G.BobPomodoroCountdown
		for _, state in ipairs(states) do
			if state.status == "missing" then
				runtime.state = {
					rawOutput = "No current Pomodoro",
					status = "missing",
					lastSyncEpoch = fixed,
				}
			else
				runtime.state = {
					rawOutput = "0900-0915 Test task",
					status = state.status,
					taskText = "— DEEP WORK",
					fullTheme = state.fullTheme,
					displayTheme = state.fullTheme,
					stopTime = state.stopTime,
					endHour = 10,
					endMinute = 15,
					endEpoch = state.endEpoch,
					lastSyncEpoch = fixed,
				}
			end
			local first_call = #env.menu_title_calls + 1
			_G.BobPomodoroCountdown.tickTimer.callback()
			_G.BobPomodoroCountdown.tickTimer.callback()
			local first_title = env.menu_title_calls[first_call].title
			local second_title = env.menu_title_calls[first_call + 1].title
			assert.equals(title_text(first_title), title_text(second_title))
			for index = first_call, first_call + 1 do
				local spans = title_spans(env.menu_title_calls[index].title)
				if spans then
					for _, span in ipairs(spans) do
						assert.is_nil(span.attributes.backgroundColor)
					end
				end
			end
		end
		restore_clock()
	end)

	it("validates converted bold fonts and resolves mono fonts once per load", function()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = {
			rawOutput = "No current Pomodoro",
			status = "missing",
			lastSyncEpoch = os.time(),
		}
		runtime.tickTimer.callback()
		runtime.tickTimer.callback()
		runtime.state = {
			rawOutput = "0900-0915 Test task",
			status = "active",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "09:15",
			endHour = 9,
			endMinute = 15,
			endEpoch = os.time() - 901,
			lastSyncEpoch = os.time(),
		}
		runtime.tickTimer.callback()
		runtime.tickTimer.callback()

		assert.equals(1, env.valid_font_calls[".SFNS-Bold"])
		assert.is_true((env.valid_font_calls["Helvetica-Bold"] or 0) >= 1)
		assert.is_true((env.valid_font_calls["Menlo-Regular"] or 0) >= 1)
		assert.is_true((env.valid_font_calls["Menlo-Bold"] or 0) >= 1)

		local missing_call = nil
		local saw_warning_flash = false
		local saw_warning_steady = false
		for _, call in ipairs(env.styled_text_calls) do
			if call.text == "NO POMODORO" then
				missing_call = call
			elseif call.text == "\194\160OVERDUE\194\160" or call.text == "OVERDUE" then
				if call.attributes.backgroundColor then
					saw_warning_flash = true
					assert.are.same({ hex = "#FFFFFF", alpha = 1 }, call.attributes.color)
					assert.are.same({ hex = "#E3413B", alpha = 1 }, call.attributes.backgroundColor)
				elseif call.text == "\194\160OVERDUE\194\160" then
					saw_warning_steady = true
					assert.are.same({ hex = "#E3413B", alpha = 1 }, call.attributes.color)
				end
			end

			local font = call.attributes and call.attributes.font
			if font then
				assert.not_equals(".SFNS-Bold", font.name)
				if font.name ~= ".AppleSystemUIFont" then
					assert.is_true((env.valid_font_calls[font.name] or 0) >= 1)
				end
			end
		end

		assert.is_not_nil(missing_call)
		assert.are.same({ hex = "#009123", alpha = 1 }, missing_call.attributes.color)
		assert.is_true(saw_warning_flash)
		assert.is_true(saw_warning_steady)
	end)

	it("leaves a complete readable title when styling fails", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = {
			rawOutput = "[<13m] 0950-1015 — DEEP WORK",
			status = "active",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "10:15",
			endHour = 10,
			endMinute = 15,
			durationMinutes = 25,
			duration = "25m",
			endEpoch = fixed + 60,
			lastSyncEpoch = fixed,
		}
		env.fail_styling = true
		runtime.tickTimer.callback()
		restore_clock()

		local title = env.menu_title_calls[#env.menu_title_calls].title
		assert.equals("string", type(title))
		assert.is_true(title:find("🍅", 1, true) ~= nil)
		assert.is_true(title:find("DEEP WORK", 1, true) ~= nil)
		assert.is_true(title:find("(25m)", 1, true) ~= nil)
	end)

	it("replaces displayed context on rename and retime", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		assert.equals("DEEP WORK", _G.BobPomodoroCountdown.state.fullTheme)

		env.task_completion = {
			exit_code = 0,
			stdout = "[<5m] 1000-1020 — FOCUS TIME",
			stderr = "",
		}
		_G.BobPomodoroCountdown.syncTimer.callback()
		restore_clock()

		local runtime = _G.BobPomodoroCountdown
		assert.equals("FOCUS TIME", runtime.state.fullTheme)
		assert.equals("10:20", runtime.state.stopTime)
		assert.equals("20m", runtime.state.duration)
		local title = title_text(runtime.menu.title)
		assert.is_true(title:find("FOCUS TIME", 1, true) ~= nil)
		assert.is_true(title:find("(20m)", 1, true) ~= nil)
		assert.is_nil(title:find("DEEP WORK", 1, true))
		assert.is_true(runtime.menu.tooltip:find("FOCUS TIME (20m)", 1, true) ~= nil)
		assert.is_true(runtime.menu.tooltip:find("Stops at 10:20", 1, true) ~= nil)
		assert.equals("FOCUS TIME (20m) → 10:20", runtime.menu.menu[1].title)
	end)

	it("clears old context on empty success and recovers on later valid output", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		assert.equals("DEEP WORK", _G.BobPomodoroCountdown.state.fullTheme)

		env.task_completion = { exit_code = 0, stdout = "   \n", stderr = "" }
		_G.BobPomodoroCountdown.syncTimer.callback()

		local runtime = _G.BobPomodoroCountdown
		assert.equals("missing", runtime.state.status)
		assert.is_nil(runtime.state.fullTheme)
		assert.is_nil(runtime.state.stopTime)
		assert.is_nil(runtime.state.duration)
		assert.equals("🍅 NO POMODORO", title_text(runtime.menu.title))
		assert.equals("No current Pomodoro", runtime.menu.tooltip)
		assert.equals("No current Pomodoro", runtime.menu.menu[1].title)
		assert.is_nil(runtime.menu.tooltip:find("DEEP WORK", 1, true))
		assert.is_nil(runtime.menu.tooltip:find("Stops at", 1, true))
		assert.is_nil(runtime.menu.tooltip:find("(25m)", 1, true))

		env.task_completion = {
			exit_code = 0,
			stdout = "[<5m] 1000-1020 — FOCUS TIME",
			stderr = "",
		}
		_G.BobPomodoroCountdown.syncTimer.callback()
		restore_clock()

		assert.equals("FOCUS TIME", runtime.state.fullTheme)
		local title = title_text(runtime.menu.title)
		assert.is_true(title:find("FOCUS TIME", 1, true) ~= nil)
	end)

	it("hides the menu on malformed output and recovers on later valid output", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		local runtime = _G.BobPomodoroCountdown
		assert.is_not_nil(runtime.state)

		active_env.task_completion = { exit_code = 0, stdout = "not a pomodoro", stderr = "" }
		runtime.syncTimer.callback()
		assert.is_nil(runtime.state)
		assert.is_true(runtime.menu.removed)
		assert.is_true(#active_env.printf_calls >= 1)

		active_env.task_completion = {
			exit_code = 0,
			stdout = "[<5m] 1000-1020 — FOCUS TIME",
			stderr = "",
		}
		runtime.syncTimer.callback()
		restore_clock()
		assert.equals("FOCUS TIME", runtime.state.fullTheme)
	end)

	it("hides the menu on nonzero exit and recovers on later valid output", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		local runtime = _G.BobPomodoroCountdown

		active_env.task_completion = { exit_code = 1, stdout = "", stderr = "boom" }
		runtime.syncTimer.callback()
		assert.is_nil(runtime.state)
		assert.is_true(runtime.menu.removed)

		active_env.task_completion = {
			exit_code = 0,
			stdout = "[<5m] 1000-1020 — FOCUS TIME",
			stderr = "",
		}
		runtime.syncTimer.callback()
		restore_clock()
		assert.equals("FOCUS TIME", runtime.state.fullTheme)
	end)

	it("starts only one sync task at a time", function()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)
		assert.equals(1, #env.tasks)

		_G.BobPomodoroCountdown.syncTimer.callback()
		assert.equals(1, #env.tasks)
	end)

	it("requests one sync when crossing zero", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)
		local runtime = _G.BobPomodoroCountdown
		env.task_completion = {
			exit_code = 0,
			stdout = "[OVERDUE by 0m] 0900-0915 — DEEP WORK",
			stderr = "",
		}

		runtime.state = {
			rawOutput = "[<1m] 0900-0915 — DEEP WORK",
			status = "active",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "09:15",
			endHour = 9,
			endMinute = 15,
			endEpoch = fixed - 1,
			lastSyncEpoch = fixed,
			zeroSyncRequested = nil,
		}
		runtime.task = nil
		local tasks_before = #env.tasks
		local old_state = runtime.state
		runtime.tickTimer.callback()
		assert.equals(tasks_before + 1, #env.tasks)
		assert.is_true(old_state.zeroSyncRequested)
		assert.equals("overdue", runtime.state.status)

		local tasks_after_first = #env.tasks
		runtime.tickTimer.callback()
		assert.equals(tasks_after_first, #env.tasks)
		restore_clock()
	end)

	it("syncs on wake and unlock", function()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)
		local runtime = _G.BobPomodoroCountdown
		runtime.task = nil
		local tasks_before = #env.tasks

		runtime.wakeWatcher.callback(_G.hs.caffeinate.watcher.systemDidWake)
		runtime.task = nil
		runtime.wakeWatcher.callback(_G.hs.caffeinate.watcher.screensDidUnlock)
		assert.equals(tasks_before + 2, #env.tasks)
	end)

	it("supports manual refresh from the menu", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		local runtime = _G.BobPomodoroCountdown
		local tasks_before = #env.tasks
		local refresh = menu_refresh_fn(runtime.menu)
		assert.is_not_nil(refresh)
		refresh()
		restore_clock()
		assert.equals(tasks_before + 1, #env.tasks)
	end)

	it("rejects stale task callbacks", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		local runtime = _G.BobPomodoroCountdown
		local first_task = env.tasks[1]
		assert.is_not_nil(first_task)

		env.task_completion = {
			exit_code = 0,
			stdout = "[<5m] 1000-1020 — FOCUS TIME",
			stderr = "",
		}
		runtime.syncTimer.callback()
		assert.equals("FOCUS TIME", runtime.state.fullTheme)

		first_task.callback(0, "[<13m] 0950-1015 — DEEP WORK", "")
		restore_clock()
		assert.equals("FOCUS TIME", runtime.state.fullTheme)
	end)
end)

describe("Hammerspoon init Pomodoro countdown gradient", function()
	after_each(function()
		if active_env then
			active_env.restore()
			active_env = nil
		end
	end)

	local LABEL_COLOR = { list = "System", name = "labelColor", alpha = 1 }

	local function running_state(fixed, remaining_seconds, minutes)
		return {
			rawOutput = "[<13m] 0950-1015 — DEEP WORK",
			status = "active",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "10:15",
			startHour = 9,
			startMinute = 50,
			endHour = 10,
			endMinute = 15,
			durationMinutes = minutes,
			duration = minutes and (minutes .. "m") or nil,
			endEpoch = fixed + remaining_seconds,
			lastSyncEpoch = fixed,
		}
	end

	local function last_spans(env)
		local title = env.menu_title_calls[#env.menu_title_calls].title
		return title_text(title), assert(title_spans(title))
	end

	local GRADIENT = {
		"#E3413B",
		"#D85100",
		"#C16400",
		"#AB7100",
		"#927C00",
		"#768500",
		"#4E8C00",
		"#009123",
		"#008F5B",
		"#008D81",
	}
	local ALERT_COLOR = "#E3413B"
	local MISSING_COLOR = "#009123"
	local BADGE_TEXT_COLOR = "#FFFFFF"

	it("paints the running countdown from one palette with bold mono digits", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)
		env.interface_style = "Dark"

		local runtime = _G.BobPomodoroCountdown
		runtime.state = running_state(fixed, 3000, 50)
		runtime.tickTimer.callback()
		restore_clock()

		local text, spans = last_spans(env)
		assert.equals("DEEP WORK (50m) · 🍅 50:00", text)
		assert.equals(7, #spans)
		assert.equals("50:00", spans[7].text)
		assert.are.same({ hex = "#008D81", alpha = 1 }, spans[7].attributes.color)
		assert.equals("Menlo-Bold", spans[7].attributes.font.name)
		assert.equals(".AppleSystemUIFont", spans[3].attributes.font.name)

		assert.are.same(LABEL_COLOR, spans[1].attributes.color)
		assert.are.same(LABEL_COLOR, spans[3].attributes.color)
		assert.are.same(LABEL_COLOR, spans[5].attributes.color)
		for _, span in ipairs(spans) do
			assert.is_nil(span.attributes.backgroundColor)
		end
		assert.equals(0, env.host_calls)
	end)

	it("ignores the system appearance, a missing host module, and host errors", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = running_state(fixed, 3000, 50)
		local hs_host = _G.hs.host

		local snapshots = {}
		local function snapshot()
			local text, spans = last_spans(env)
			local colors = {}
			local fonts = {}
			local texts = {}
			for index, span in ipairs(spans) do
				texts[index] = span.text
				colors[index] = span.attributes.color
				fonts[index] = span.attributes.font
			end
			return { text = text, count = #spans, texts = texts, colors = colors, fonts = fonts }
		end

		env.interface_style = "Dark"
		runtime.tickTimer.callback()
		table.insert(snapshots, snapshot())

		env.interface_style = nil
		runtime.tickTimer.callback()
		table.insert(snapshots, snapshot())

		env.interface_style = "Light"
		runtime.tickTimer.callback()
		table.insert(snapshots, snapshot())

		env.interface_style = "Solarized"
		runtime.tickTimer.callback()
		table.insert(snapshots, snapshot())

		_G.hs.host = nil
		runtime.tickTimer.callback()
		table.insert(snapshots, snapshot())

		_G.hs.host = hs_host
		env.host_error = "boom"
		runtime.tickTimer.callback()
		restore_clock()
		table.insert(snapshots, snapshot())

		for index = 2, #snapshots do
			assert.equals(snapshots[1].text, snapshots[index].text)
			assert.equals(snapshots[1].count, snapshots[index].count)
			assert.are.same(snapshots[1].texts, snapshots[index].texts)
			assert.are.same(snapshots[1].colors, snapshots[index].colors)
			assert.are.same(snapshots[1].fonts, snapshots[index].fonts)
		end
		assert.equals("DEEP WORK (50m) · 🍅 50:00", snapshots[1].text)
		assert.are.same({ hex = GRADIENT[10], alpha = 1 }, snapshots[1].colors[#snapshots[1].colors])
		assert.equals("Menlo-Bold", snapshots[1].fonts[#snapshots[1].fonts].name)
		assert.equals(0, env.host_calls)
	end)

	it("falls back to neutral countdown text without a numeric duration", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)
		env.interface_style = "Dark"

		local runtime = _G.BobPomodoroCountdown
		runtime.state = running_state(fixed, 60, nil)
		runtime.state.duration = nil
		runtime.state.durationMinutes = nil
		runtime.tickTimer.callback()
		restore_clock()

		local text, spans = last_spans(env)
		assert.equals("DEEP WORK → 10:15 · 🍅 01:00", text)
		assert.are.same(LABEL_COLOR, spans[#spans].attributes.color)
		assert.equals("Menlo-Bold", spans[#spans].attributes.font.name)
		assert.equals(0, env.host_calls)
	end)

	it("paints overdue countdowns and badges from the vetted band", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = running_state(fixed, -1, 15)
		runtime.state.status = "overdue"
		runtime.state.zeroSyncRequested = true
		runtime.state.endEpoch = fixed - 1
		runtime.tickTimer.callback()
		local _, overdue_spans = last_spans(env)
		assert.are.same({ hex = ALERT_COLOR, alpha = 1 }, overdue_spans[#overdue_spans].attributes.color)
		assert.equals("Menlo-Bold", overdue_spans[#overdue_spans].attributes.font.name)

		runtime.state = {
			rawOutput = "[OVERDUE by 15m] 0900-0915 — DEEP WORK",
			status = "overdue",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "09:15",
			endHour = 9,
			endMinute = 15,
			durationMinutes = 15,
			duration = "15m",
			endEpoch = fixed - 901,
			lastSyncEpoch = fixed,
		}
		runtime.tickTimer.callback()
		local _, steady_spans = last_spans(env)
		runtime.tickTimer.callback()
		restore_clock()
		local _, flash_spans = last_spans(env)

		local steady, flash = steady_spans[#steady_spans], flash_spans[#flash_spans]
		if steady.attributes.backgroundColor ~= nil then
			steady, flash = flash, steady
		end
		assert.is_nil(steady.attributes.backgroundColor)
		assert.are.same({ hex = ALERT_COLOR, alpha = 1 }, steady.attributes.color)
		assert.are.same({ hex = BADGE_TEXT_COLOR, alpha = 1 }, flash.attributes.color)
		assert.are.same({ hex = ALERT_COLOR, alpha = 1 }, flash.attributes.backgroundColor)
	end)

	it("paints the missing state from the vetted band", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = {
			rawOutput = "No current Pomodoro",
			status = "missing",
			lastSyncEpoch = fixed,
		}
		runtime.tickTimer.callback()
		restore_clock()

		local text, spans = last_spans(env)
		assert.equals("🍅 NO POMODORO", text)
		local missing_span = nil
		for _, span in ipairs(spans) do
			if span.text == "NO POMODORO" then
				missing_span = span
			end
		end
		assert.is_not_nil(missing_span)
		assert.are.same({ hex = MISSING_COLOR, alpha = 1 }, missing_span.attributes.color)
	end)

	it("falls back to regular mono when Menlo-Bold is unavailable", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with({ invalid_fonts = { ["Menlo-Bold"] = true } })
		assert.is_true(ok, error_message)
		assert.equals(1, env.valid_font_calls["Menlo-Bold"])
		local calls_after_load = env.valid_font_calls["Menlo-Bold"]

		local runtime = _G.BobPomodoroCountdown
		runtime.state = running_state(fixed, 3000, 50)
		runtime.tickTimer.callback()
		local running_text, running_spans = last_spans(env)
		assert.equals("DEEP WORK (50m) · 🍅 50:00", running_text)
		assert.are.same({ hex = GRADIENT[10], alpha = 1 }, running_spans[#running_spans].attributes.color)
		assert.equals("Menlo-Regular", running_spans[#running_spans].attributes.font.name)

		runtime.state = running_state(fixed, 60, nil)
		runtime.state.duration = nil
		runtime.state.durationMinutes = nil
		runtime.tickTimer.callback()
		local _, neutral_spans = last_spans(env)
		assert.are.same(LABEL_COLOR, neutral_spans[#neutral_spans].attributes.color)
		assert.equals("Menlo-Regular", neutral_spans[#neutral_spans].attributes.font.name)

		runtime.state = running_state(fixed, -1, 15)
		runtime.state.status = "overdue"
		runtime.state.zeroSyncRequested = true
		runtime.state.endEpoch = fixed - 1
		runtime.tickTimer.callback()
		restore_clock()
		local _, overdue_spans = last_spans(env)
		assert.are.same({ hex = ALERT_COLOR, alpha = 1 }, overdue_spans[#overdue_spans].attributes.color)
		assert.equals("Menlo-Regular", overdue_spans[#overdue_spans].attributes.font.name)

		assert.equals(calls_after_load, env.valid_font_calls["Menlo-Bold"])
	end)

	it("carries durationMinutes from sync into gradient selection without an extra request", function()
		local restore_clock = freeze_clock_at(today_at(9, 50))
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		env.interface_style = "Dark"

		local runtime = _G.BobPomodoroCountdown
		assert.equals(25, runtime.state.durationMinutes)
		assert.equals("25m", runtime.state.duration)

		local tasks_before = #env.tasks
		runtime.tickTimer.callback()
		local full_text, full_spans = last_spans(env)
		assert.equals("DEEP WORK (25m) · 🍅 25:00", full_text)
		assert.are.same({ hex = "#008D81", alpha = 1 }, full_spans[#full_spans].attributes.color)

		runtime.state.endEpoch = runtime.state.endEpoch - 150
		runtime.tickTimer.callback()
		restore_clock()
		assert.equals(tasks_before, #env.tasks)
		local boundary_text, boundary_spans = last_spans(env)
		assert.equals("DEEP WORK (25m) · 🍅 22:30", boundary_text)
		assert.are.same({ hex = "#008F5B", alpha = 1 }, boundary_spans[#boundary_spans].attributes.color)
	end)

	it("updates the gradient denominator on retime while rename-only keeps the color", function()
		local restore_clock = freeze_clock_at(today_at(10, 10))
		local ok, error_message, env = load_init_with({
			task_completion = {
				exit_code = 0,
				stdout = "[<13m] 0950-1015 — DEEP WORK",
				stderr = "",
			},
		})
		assert.is_true(ok, error_message)
		env.interface_style = "Dark"

		local runtime = _G.BobPomodoroCountdown
		runtime.tickTimer.callback()
		local _, first_spans = last_spans(env)
		assert.equals(25, runtime.state.durationMinutes)
		assert.are.same({ hex = "#D85100", alpha = 1 }, first_spans[#first_spans].attributes.color)

		env.task_completion = {
			exit_code = 0,
			stdout = "[<5m] 1000-1020 — FOCUS TIME",
			stderr = "",
		}
		runtime.syncTimer.callback()
		assert.equals(20, runtime.state.durationMinutes)
		assert.equals("20m", runtime.state.duration)
		local retime_text, retime_spans = last_spans(env)
		assert.is_true(retime_text:find("FOCUS TIME (20m) · 🍅 10:00", 1, true) ~= nil)
		assert.are.same({ hex = "#927C00", alpha = 1 }, retime_spans[#retime_spans].attributes.color)

		env.task_completion = {
			exit_code = 0,
			stdout = "[<5m] 1000-1020 — DEEP REST",
			stderr = "",
		}
		runtime.syncTimer.callback()
		restore_clock()
		local rename_text, rename_spans = last_spans(env)
		assert.is_true(rename_text:find("DEEP REST (20m) · 🍅 10:00", 1, true) ~= nil)
		assert.are.same(retime_spans[#retime_spans].attributes.color, rename_spans[#rename_spans].attributes.color)
	end)

	it("audits every painted color against the vetted set", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		local vetted = {}
		for _, hex in ipairs(GRADIENT) do
			vetted[hex] = true
		end
		vetted[ALERT_COLOR] = true
		vetted[MISSING_COLOR] = true
		vetted[BADGE_TEXT_COLOR] = true

		local seen_stops = {}
		local function audit_current_title()
			local title = env.menu_title_calls[#env.menu_title_calls].title
			local spans = assert(title_spans(title))
			for _, span in ipairs(spans) do
				local attributes = assert(span.attributes)
				local color = attributes.color
				if color.hex then
					assert.equals(1, color.alpha)
					assert.is_true(vetted[color.hex] == true, "unvetted foreground " .. color.hex)
					if color.hex == BADGE_TEXT_COLOR then
						assert.are.same(
							{ hex = ALERT_COLOR, alpha = 1 },
							attributes.backgroundColor,
							"badge text outside alert background"
						)
					end
					if GRADIENT[10] == color.hex or vetted[color.hex] then
						for bucket = 1, 10 do
							if GRADIENT[bucket] == color.hex then
								seen_stops[bucket] = true
							end
						end
					end
				else
					assert.are.same(LABEL_COLOR, color)
				end
				local background = attributes.backgroundColor
				if background ~= nil then
					assert.are.same({ hex = ALERT_COLOR, alpha = 1 }, background)
				end
			end
		end

		local remaining_by_bucket = { 300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000 }
		for bucket = 1, 10 do
			runtime.state = running_state(fixed, remaining_by_bucket[bucket], 50)
			runtime.tickTimer.callback()
			audit_current_title()
		end

		runtime.state = running_state(fixed, 60, nil)
		runtime.state.duration = nil
		runtime.state.durationMinutes = nil
		runtime.tickTimer.callback()
		audit_current_title()

		runtime.state = running_state(fixed, -1, 15)
		runtime.state.status = "overdue"
		runtime.state.zeroSyncRequested = true
		runtime.state.endEpoch = fixed - 1
		runtime.tickTimer.callback()
		audit_current_title()

		runtime.state = {
			rawOutput = "[OVERDUE by 15m] 0900-0915 — DEEP WORK",
			status = "overdue",
			taskText = "— DEEP WORK",
			fullTheme = "DEEP WORK",
			displayTheme = "DEEP WORK",
			stopTime = "09:15",
			endHour = 9,
			endMinute = 15,
			durationMinutes = 15,
			duration = "15m",
			endEpoch = fixed - 901,
			lastSyncEpoch = fixed,
		}
		runtime.tickTimer.callback()
		audit_current_title()
		runtime.tickTimer.callback()
		audit_current_title()

		runtime.state = {
			rawOutput = "No current Pomodoro",
			status = "missing",
			lastSyncEpoch = fixed,
		}
		runtime.tickTimer.callback()
		restore_clock()
		audit_current_title()

		for bucket = 1, 10 do
			assert.is_true(seen_stops[bucket] == true, "bucket " .. bucket .. " never painted")
		end
		assert.equals(0, env.host_calls)
	end)

	it("leaves complete plain titles with the relocated tomato when styling fails", function()
		local restore_clock, fixed = freeze_clock()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		env.fail_styling = true

		runtime.state = running_state(fixed, 60, 25)
		runtime.tickTimer.callback()
		local running_title = env.menu_title_calls[#env.menu_title_calls].title
		assert.equals("string", type(running_title))
		assert.equals("DEEP WORK (25m) · 🍅 01:00", running_title)

		runtime.state = running_state(fixed, -1, 25)
		runtime.state.status = "overdue"
		runtime.state.zeroSyncRequested = true
		runtime.tickTimer.callback()
		local overdue_title = env.menu_title_calls[#env.menu_title_calls].title
		assert.equals("string", type(overdue_title))
		assert.equals("DEEP WORK (25m) → 10:15 · 🍅 +00:01", overdue_title)

		runtime.state = {
			rawOutput = "No current Pomodoro",
			status = "missing",
			lastSyncEpoch = fixed,
		}
		runtime.tickTimer.callback()
		restore_clock()
		local missing_title = env.menu_title_calls[#env.menu_title_calls].title
		assert.equals("string", type(missing_title))
		assert.equals("🍅 NO POMODORO", missing_title)
	end)
end)
