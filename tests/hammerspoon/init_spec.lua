local INIT_PATH = "home/dot_hammerspoon/init.lua"

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

	hs.styledtext = {
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
			return name ~= ".SFNS-Bold"
		end,
		new = function(text, attributes)
			table.insert(env.styled_text_calls, {
				text = text,
				attributes = attributes,
			})
			return {
				text = text,
				attributes = attributes,
			}
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

local function default_presentation(remaining_seconds)
	if remaining_seconds == nil then
		return {
			title = "NO POMODORO",
			appearance = "missing",
		}
	end
	if remaining_seconds <= -600 then
		return {
			title = "OVERDUE POMODORO",
			appearance = "overdue_warning",
		}
	end
	if remaining_seconds < 0 then
		return {
			title = "+0:01",
			appearance = "overdue",
		}
	end
	return {
		title = "0:01",
		appearance = "normal",
	}
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
		convert_font_calls = {},
		valid_font_calls = {},
		task_completion = options.task_completion,
		reload_calls = 0,
	}

	_G.hs = make_hs(env)
	_G.BobPomodoroCountdown = options.runtime
	package.loaded.pomodoro_countdown = {
		presentation = options.presentation or default_presentation,
	}
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

	it("validates converted bold fonts before styled Pomodoro warning renders", function()
		local ok, error_message, env = load_init_with()
		assert.is_true(ok, error_message)

		local runtime = _G.BobPomodoroCountdown
		runtime.state = {
			rawOutput = "No current Pomodoro",
			status = "missing",
			lastSyncEpoch = os.time(),
		}
		runtime.tickTimer.callback()
		runtime.state = {
			rawOutput = "0900-0915 Test task",
			status = "active",
			endEpoch = os.time() - 601,
			lastSyncEpoch = os.time(),
		}
		runtime.tickTimer.callback()

		assert.equals(1, env.valid_font_calls[".SFNS-Bold"])
		assert.is_true((env.valid_font_calls["Helvetica-Bold"] or 0) >= 1)

		local missing_call = nil
		local overdue_warning_call = nil
		for _, call in ipairs(env.styled_text_calls) do
			if call.text == "NO POMODORO" then
				missing_call = call
			elseif call.text == "OVERDUE POMODORO" then
				overdue_warning_call = call
			end

			local font = call.attributes and call.attributes.font
			if font then
				assert.not_equals(".SFNS-Bold", font.name)
				assert.is_true((env.valid_font_calls[font.name] or 0) >= 1)
			end
		end

		assert.is_not_nil(missing_call)
		assert.are.same({ hex = "#30d158", alpha = 1 }, missing_call.attributes.color)
		assert.is_not_nil(overdue_warning_call)
		assert.are.same({ hex = "#ff453a", alpha = 1 }, overdue_warning_call.attributes.color)
	end)
end)
