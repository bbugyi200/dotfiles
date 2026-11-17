local PING_WINDOW_PATH = "home/dot_hammerspoon/ping_window.lua"
local PING_INDICATOR_PATH = "home/dot_hammerspoon/ping_indicator.lua"

local NBSP = "\194\160" -- U+00A0
local FIGURE_SPACE = "\226\128\135" -- U+2007

local PING_ARGS = { "-n", "-q", "-c", "1", "-W", "500", "8.8.8.8" }
local NETWORK_SETTINGS_URL = "x-apple.systempreferences:com.apple.Network-Settings.extension"
local SYSTEM_SETTINGS_BUNDLE_ID = "com.apple.systempreferences"

local SUCCESS_TRANSCRIPT = table.concat({
	"PING 8.8.8.8 (8.8.8.8): 56 data bytes",
	"64 bytes from 8.8.8.8: icmp_seq=0 ttl=117 time=18.345 ms",
	"",
	"--- 8.8.8.8 ping statistics ---",
	"1 packets transmitted, 1 packets received, 0.0% packet loss",
	"round-trip min/avg/max/stddev = 18.123/18.345/18.567/0.222 ms",
	"",
}, "\n")

local TIMEOUT_TRANSCRIPT = table.concat({
	"PING 8.8.8.8 (8.8.8.8): 56 data bytes",
	"",
	"--- 8.8.8.8 ping statistics ---",
	"1 packets transmitted, 0 packets received, 100.0% packet loss",
	"",
}, "\n")

local SLOW_TRANSCRIPT = table.concat({
	"PING 8.8.8.8 (8.8.8.8): 56 data bytes",
	"64 bytes from 8.8.8.8: icmp_seq=0 ttl=117 time=2100.000 ms",
	"",
	"--- 8.8.8.8 ping statistics ---",
	"1 packets transmitted, 1 packets received, 0.0% packet loss",
	"round-trip min/avg/max/stddev = 2050.000/2100.000/2150.000/25.000 ms",
	"",
}, "\n")

local CURL_OK = "Success\n__PING_WINDOW__ 200 0.010 0.130"
local CURL_PORTAL = "Sign in\n__PING_WINDOW__ 302 0.010 0.020"

local function make_task(env, command, callback, args)
	local task = {
		command = command,
		callback = callback,
		args = args,
		started = false,
		start_calls = 0,
		terminated = false,
		completed = false,
	}

	function task:start()
		if env.task_start_throw_command == self.command then
			error("injected task start failure")
		end
		self.started = true
		self.start_calls = self.start_calls + 1
		if env.task_start_false_command == self.command then
			return false
		end
		return self
	end

	function task:terminate()
		self.terminated = true
	end

	function task:isRunning()
		return not self.completed and not self.terminated
	end

	function task:complete(exit_code, stdout, stderr)
		self.completed = true
		self.callback(exit_code, stdout, stderr)
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

	hs.task = {
		new = function(command, callback, args)
			if env.task_new_nil or env.task_new_nil_command == command then
				return nil
			end
			return make_task(env, command, callback, args)
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
			function timer:start()
				self.started = true
				return self
			end
			function timer:stop()
				self.started = false
				self.stop_calls = self.stop_calls + 1
			end
			table.insert(env.do_after, timer)
			return timer
		end,
	}

	hs.menubar = {
		new = function(in_menu_bar, autosave_name)
			local menu = {
				in_menu_bar = in_menu_bar,
				autosave_name = autosave_name,
				title = nil,
				tooltip = nil,
				menu_builder = nil,
				set_menu_calls = 0,
				returned = false,
				removed = false,
			}
			function menu:setTitle(title)
				self.title = title
				table.insert(env.menu_titles, title)
				return self
			end
			function menu:setTooltip(tooltip)
				self.tooltip = tooltip
				return self
			end
			function menu:setMenu(builder)
				self.menu_builder = builder
				self.set_menu_calls = self.set_menu_calls + 1
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
			table.insert(env.menus, menu)
			return menu
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

	hs.fs = {
		attributes = function(path)
			table.insert(env.fs_attribute_calls, path)
			if env.fs_attributes_nil then
				return nil
			end
			return { mode = "directory" }
		end,
		mkdir = function(path)
			table.insert(env.mkdir_calls, path)
			if env.fs_mkdir_fail then
				return nil, "boom"
			end
			return true
		end,
	}

	hs.urlevent = {
		openURLWithBundle = function(url, bundle)
			table.insert(env.opened_bundle_urls, { url = url, bundle = bundle })
			if env.open_bundle_throw ~= nil then
				error(env.open_bundle_throw)
			end
			if env.open_bundle_result ~= nil then
				return env.open_bundle_result
			end
			return true
		end,
		openURL = function(url)
			error("openURL must not be used for Network Settings: " .. tostring(url))
		end,
	}

	hs.alert = {
		show = function(message, duration)
			table.insert(env.alerts, message)
			table.insert(env.alert_calls, { message = message, duration = duration })
			return true
		end,
	}

	hs.pasteboard = {
		setContents = function(text)
			if env.pasteboard_throw then
				error(env.pasteboard_throw)
			end
			if env.pasteboard_false then
				return false
			end
			env.pasteboard_value = text
			table.insert(env.pasteboard_writes, text)
			return true
		end,
	}

	hs.eventtap = {
		checkKeyboardModifiers = function()
			if env.modifiers_throw then
				error(env.modifiers_throw)
			end
			return env.held_modifiers or {}
		end,
	}

	hs.styledtext = make_styledtext(env)

	function hs.printf(...)
		table.insert(env.printf_calls, { ... })
	end

	return hs
end

local function setup(options)
	options = options or {}
	local tmp_base = os.tmpname()
	os.remove(tmp_base)
	local env = {
		previous_hs = _G.hs,
		previous_runtime = _G.BobPingIndicator,
		previous_window_module = package.loaded.ping_window,
		tasks = {},
		timers = {},
		do_after = {},
		menus = {},
		menu_titles = {},
		printf_calls = {},
		styled_text_calls = {},
		styled_compositions = {},
		convert_font_calls = {},
		valid_font_calls = {},
		opened_bundle_urls = {},
		alerts = {},
		alert_calls = {},
		pasteboard_writes = {},
		held_modifiers = {},
		open_bundle_result = options.open_bundle_result,
		open_bundle_throw = options.open_bundle_throw,
		fs_attribute_calls = {},
		mkdir_calls = {},
		now = options.now or 1759680002,
		state_path = tmp_base .. "_ping_state",
		events_path = tmp_base .. "_ping_events",
		config_path = tmp_base .. "_ping_config",
		session_properties = options.session_properties,
		session_throw = options.session_throw,
		task_new_nil = options.task_new_nil,
		task_new_nil_command = options.task_new_nil_command,
		task_start_false_command = options.task_start_false_command,
		task_start_throw_command = options.task_start_throw_command,
		fs_attributes_nil = options.fs_attributes_nil,
		fs_mkdir_fail = options.fs_mkdir_fail,
		fail_styling = false,
	}

	function env.now_fn()
		return env.now
	end

	function env.restore()
		_G.hs = env.previous_hs
		_G.BobPingIndicator = env.previous_runtime
		package.loaded.ping_window = env.previous_window_module
		package.loaded.ping_indicator = nil
		pcall(os.remove, env.state_path)
		pcall(os.remove, env.state_path .. ".tmp.hammerspoon")
		pcall(os.remove, env.events_path)
		pcall(os.remove, env.events_path .. ".tmp.hammerspoon")
		pcall(os.remove, env.config_path)
	end

	_G.hs = make_hs(env)
	_G.BobPingIndicator = nil
	package.loaded.ping_window = assert(loadfile(PING_WINDOW_PATH))()
	local indicator = assert(loadfile(PING_INDICATOR_PATH))()
	return env, indicator
end

local function start_indicator(env, indicator)
	indicator.start({
		state_path = env.state_path,
		events_path = env.events_path,
		ping_path = "/sbin/ping",
		config_path = env.config_path,
		now = env.now_fn,
	})
end

local function write_config_file(env, text)
	local handle = assert(io.open(env.config_path, "w"))
	handle:write(text)
	handle:close()
end

local function read_state_file(env)
	local handle = io.open(env.state_path, "r")
	if not handle then
		return nil
	end
	local text = handle:read("*a")
	handle:close()
	return text
end

local function write_state_file(env, text)
	local handle = assert(io.open(env.state_path, "w"))
	handle:write(text)
	handle:close()
end

local function fire_tick(env)
	env.timers[#env.timers].callback()
end

local function complete_latest(env, exit_code, stdout, stderr)
	env.tasks[#env.tasks]:complete(exit_code, stdout, stderr or "")
end

local function latest_task(env, command)
	for index = #env.tasks, 1, -1 do
		if command == nil or env.tasks[index].command == command then
			return env.tasks[index]
		end
	end
	error("task not found: " .. tostring(command))
end

local function complete_task(task, exit_code, stdout, stderr)
	task:complete(exit_code, stdout, stderr or "")
end

local function read_events(env)
	local handle = io.open(env.events_path, "r")
	if not handle then
		return ""
	end
	local text = handle:read("*a")
	handle:close()
	return text
end

local function event_lines(env)
	local lines = {}
	for line in read_events(env):gmatch("([^\n]+)") do
		table.insert(lines, line)
	end
	return lines
end

local function write_events(env, count)
	local handle = assert(io.open(env.events_path, "w"))
	for index = 1, count do
		handle:write(string.format("old-%d\tseed\tvalue=%d\n", index, index))
	end
	handle:close()
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

local function span_with_text(spans, needle)
	for _, span in ipairs(spans) do
		if type(span.text) == "string" and span.text:find(needle, 1, true) then
			return span
		end
	end
	return nil
end

local function logged_message(env, needle)
	for _, call in ipairs(env.printf_calls) do
		for _, part in ipairs(call) do
			if tostring(part):find(needle, 1, true) then
				return true
			end
		end
	end
	return false
end

local function count_logs(env, needle)
	local count = 0
	for _, call in ipairs(env.printf_calls) do
		for _, part in ipairs(call) do
			if tostring(part):find(needle, 1, true) then
				count = count + 1
				break
			end
		end
	end
	return count
end

local function item_title(item)
	return title_text(item and item.title)
end

local function find_menu_item(items, title)
	for i = #items, 1, -1 do
		if item_title(items[i]) == title then
			return items[i]
		end
	end
	error(title .. " item not found")
end

local function network_settings_item(env, indicator)
	return find_menu_item(env.menus[1].menu_builder(), "Network Settings…")
end

local function copy_diagnostics_item(env)
	return find_menu_item(env.menus[1].menu_builder(), "Copy Diagnostics")
end

local function fire_do_after(env)
	local timer = env.do_after[#env.do_after]
	assert.is_not_nil(timer)
	timer.callback()
end

describe("Hammerspoon ping indicator startup", function()
	local env = nil

	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("creates one menu, one 2 s timer, and an immediate ping task", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)

		assert.equals(1, #env.menus)
		local menu = env.menus[1]
		assert.is_true(menu.in_menu_bar)
		assert.equals("BobPingIndicator", menu.autosave_name)

		assert.equals(1, #env.timers)
		assert.equals(2, env.timers[1].interval)
		assert.is_true(env.timers[1].started)

		assert.equals(1, #env.tasks)
		local task = env.tasks[1]
		assert.equals("/sbin/ping", task.command)
		assert.same(PING_ARGS, task.args)
		assert.is_true(task.started)
	end)

	it("writes the sample on success with a green title and the RTT tooltip", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		assert.equals(string.format("%d hammerspoon %d 1 rtt=18\n", env.now, env.now), read_state_file(env))

		local text = title_text(env.menus[1].title)
		assert.equals(NBSP .. "✓" .. " " .. FIGURE_SPACE .. FIGURE_SPACE .. "1/1" .. NBSP, text)

		local spans = assert(title_spans(env.menus[1].title))
		local glyph = assert(span_with_text(spans, "✓"))
		assert.are.same({ hex = "#30d158", alpha = 1 }, glyph.attributes.color)
		local count = assert(span_with_text(spans, "1/1"))
		assert.equals("Menlo-Regular", count.attributes.font.name)
		assert.are.same({ list = "System", name = "labelColor", alpha = 1 }, count.attributes.color)

		assert.equals("Internet: online · 1 of 1 pings answered (100%) · last reply 18 ms", env.menus[1].tooltip)
	end)

	it("waits for a web verdict before escalating three misses to the pill", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)

		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local first_text = title_text(env.menus[1].title)
		assert.is_true(first_text:find("✗", 1, true) ~= nil)
		local first_spans = assert(title_spans(env.menus[1].title))
		local first_glyph = assert(span_with_text(first_spans, "✗"))
		assert.are.same({ hex = "#E3413B", alpha = 1 }, first_glyph.attributes.color)
		local first_count = assert(span_with_text(first_spans, "0/1"))
		assert.are.same({ hex = "#E3413B", alpha = 1 }, first_count.attributes.color)
		assert.is_nil(first_count.attributes.backgroundColor)

		for _ = 1, 2 do
			env.now = env.now + 2
			fire_tick(env)
			complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		end

		assert.equals(
			string.format("%d hammerspoon %d 000 check=%d\n", env.now, env.now, env.now - 4),
			read_state_file(env)
		)
		assert.is_true(title_text(env.menus[1].title):find("✗", 1, true) ~= nil)
		local checking_spans = assert(title_spans(env.menus[1].title))
		assert.is_nil(checking_spans[1].attributes.backgroundColor)

		complete_task(latest_task(env, "/usr/bin/curl"), 28, "")
		assert.equals(
			string.format("%d hammerspoon %d 000 web=fail,%d,-\n", env.now, env.now, env.now),
			read_state_file(env)
		)
		local pill_spans = assert(title_spans(env.menus[1].title))
		assert.equals(5, #pill_spans)
		for _, span in ipairs(pill_spans) do
			assert.are.same({ hex = "#FFFFFF", alpha = 1 }, span.attributes.color)
			assert.are.same({ hex = "#E3413B", alpha = 1 }, span.attributes.backgroundColor)
		end
	end)

	it("falls back to the plain title when styling fails", function()
		local indicator
		env, indicator = setup()
		env.fail_styling = true
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		local title = env.menus[1].title
		assert.equals("string", type(title))
		assert.equals(NBSP .. "✓" .. " " .. FIGURE_SPACE .. FIGURE_SPACE .. "1/1" .. NBSP, title)
	end)
end)

describe("Hammerspoon ping indicator producer loop", function()
	local env = nil

	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("appends to an existing tmux window", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d tmux %d 0111\n", env.now - 10, env.now - 10))
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(string.format("%d hammerspoon %d 01111 rtt=18\n", env.now, env.now), read_state_file(env))
	end)

	it("appends at the gap edge and resets past it", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d tmux %d 0111\n", env.now - 60, env.now - 60))
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(string.format("%d hammerspoon %d 01111 rtt=18\n", env.now, env.now), read_state_file(env))
	end)

	it("resets the window after a long gap", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d tmux %d 0111\n", env.now - 61, env.now - 61))
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(string.format("%d hammerspoon %d 1 rtt=18\n", env.now, env.now), read_state_file(env))
	end)

	it("starts no new task while one is running and terminates it after 3 intervals", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)

		fire_tick(env)
		assert.equals(1, #env.tasks)
		assert.is_false(env.tasks[1].terminated)

		env.now = env.now + 6
		fire_tick(env)
		assert.equals(1, #env.tasks)
		assert.is_true(env.tasks[1].terminated)
		assert.is_true(logged_message(env, "terminated a ping"))

		fire_tick(env)
		assert.equals(2, #env.tasks)
	end)

	it("pauses while locked, keeps the heartbeat, and pings after unlock", function()
		local indicator
		env, indicator = setup({
			session_properties = { CGSSessionScreenIsLocked = true, kCGSSessionOnConsoleKey = true },
		})
		write_state_file(env, string.format("%d hammerspoon %d 11\n", env.now - 4, env.now - 4))
		start_indicator(env, indicator)

		assert.equals(0, #env.tasks)
		assert.equals(string.format("%d hammerspoon %d 11\n", env.now, env.now - 4), read_state_file(env))

		env.session_properties = { CGSSessionScreenIsLocked = false, kCGSSessionOnConsoleKey = true }
		env.now = env.now + 2
		fire_tick(env)
		assert.equals(1, #env.tasks)
	end)

	it("pauses while off the console", function()
		local indicator
		env, indicator = setup({
			session_properties = { CGSSessionScreenIsLocked = false, kCGSSessionOnConsoleKey = false },
		})
		write_state_file(env, string.format("%d tmux %d 0111\n", env.now - 10, env.now - 10))
		start_indicator(env, indicator)

		assert.equals(0, #env.tasks)
		assert.equals(string.format("%d hammerspoon %d 0111\n", env.now, env.now - 10), read_state_file(env))
	end)

	it("pings when the session state is unavailable", function()
		local indicator
		env, indicator = setup({ session_throw = "boom" })
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
	end)

	it("claims the stream without pinging on a fresh tmux sample", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d tmux %d 0111\n", env.now, env.now))
		start_indicator(env, indicator)

		assert.equals(0, #env.tasks)
		assert.equals(string.format("%d hammerspoon %d 0111\n", env.now, env.now), read_state_file(env))
		assert.is_true(env.menus[1].returned)
	end)

	it("renders from the file when the ping task cannot be created", function()
		local indicator
		env, indicator = setup({ task_new_nil = true })
		local before = string.format("%d hammerspoon %d 11\n", env.now, env.now)
		write_state_file(env, before)
		start_indicator(env, indicator)

		assert.equals(0, #env.tasks)
		assert.is_true(logged_message(env, "could not be created"))
		assert.equals(before, read_state_file(env))
		assert.is_true(title_text(env.menus[1].title):find("2/2", 1, true) ~= nil)
	end)

	it("logs an unwritable state directory without crashing", function()
		local indicator
		env, indicator = setup({ fs_attributes_nil = true, fs_mkdir_fail = true })
		env.state_path = env.state_path .. "_missing/state"
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		assert.is_true(logged_message(env, "could not create state directory"))
		assert.is_nil(read_state_file(env))
		assert.is_true(title_text(env.menus[1].title):find("◌", 1, true) ~= nil)
	end)

	it("stops old objects and reuses the menu on reload", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		local old_menu = env.menus[1]
		local old_timer = env.timers[1]
		local old_task = env.tasks[1]
		assert.equals(1, old_menu.set_menu_calls)

		start_indicator(env, indicator)

		assert.equals(1, old_timer.stop_calls)
		assert.is_true(old_task.terminated)
		assert.equals(1, #env.menus)
		assert.equals(old_menu, env.menus[1])
		assert.equals(2, #env.timers)
		assert.is_true(env.timers[2].started)
		assert.equals(2, #env.tasks)
		assert.equals(2, old_menu.set_menu_calls)
		assert.equals("function", type(old_menu.menu_builder))
	end)
end)

describe("Hammerspoon v2 producer", function()
	local env = nil

	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("records slow samples and RTTs, then skips tool errors", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d hammerspoon %d 1 rtt=480\n", env.now - 2, env.now - 2))
		start_indicator(env, indicator)
		complete_latest(env, 0, SLOW_TRANSCRIPT)
		assert.equals(string.format("%d hammerspoon %d 1s rtt=480,2100\n", env.now, env.now), read_state_file(env))

		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 64, "ping: invalid option")
		assert.equals(string.format("%d hammerspoon %d 1s rtt=480,2100\n", env.now, env.now - 2), read_state_file(env))
		assert.is_true(read_events(env):find("\tprobe\ttool=ping exit=64", 1, true) ~= nil)

		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 0, "1 packets transmitted, 1 packets received")
		assert.equals(string.format("%d hammerspoon %d 1s1 rtt=480,2100\n", env.now, env.now), read_state_file(env))
	end)

	it("rate-limits repeated probe errors by exit code", function()
		local indicator
		env, indicator = setup()
		local first_error_at = env.now
		start_indicator(env, indicator)
		complete_latest(env, 64, "ping: invalid option")
		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 64, "ping: invalid option")
		assert.equals(1, count_logs(env, "probe\ttool=ping exit=64"))

		env.now = first_error_at + 600
		fire_tick(env)
		complete_latest(env, 64, "ping: invalid option")
		assert.equals(2, count_logs(env, "probe\ttool=ping exit=64"))
	end)

	it("starts a rate-limited web check with the miss write and carries it while in flight", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		local first_check_at = env.now
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local curl = latest_task(env, "/usr/bin/curl")
		assert.same(package.loaded.ping_window.CURL_ARGS, curl.args)
		assert.equals(
			string.format("%d hammerspoon %d 0 check=%d\n", env.now, env.now, first_check_at),
			read_state_file(env)
		)

		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local curl_count = 0
		for _, task in ipairs(env.tasks) do
			if task.command == "/usr/bin/curl" then
				curl_count = curl_count + 1
			end
		end
		assert.equals(1, curl_count)
		assert.is_true(read_state_file(env):find("check=" .. first_check_at, 1, true) ~= nil)

		complete_task(curl, 0, CURL_OK)
		assert.is_true(read_state_file(env):find("web=ok," .. env.now .. ",120", 1, true) ~= nil)
		assert.is_nil(read_state_file(env):find("check=", 1, true))

		env.now = first_check_at + 9
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		assert.equals(
			1,
			(function()
				local count = 0
				for _, task in ipairs(env.tasks) do
					if task.command == "/usr/bin/curl" then
						count = count + 1
					end
				end
				return count
			end)()
		)

		env.now = first_check_at + 10
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local curl_count = 0
		for _, task in ipairs(env.tasks) do
			if task.command == "/usr/bin/curl" then
				curl_count = curl_count + 1
			end
		end
		assert.equals(2, curl_count)
		assert.is_true(read_state_file(env):find("check=" .. env.now, 1, true) ~= nil)
	end)

	it("does not persist a check token when curl cannot be launched", function()
		local indicator
		env, indicator = setup({ task_new_nil_command = "/usr/bin/curl" })
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		assert.is_nil(read_state_file(env):find("check=", 1, true))
		assert.equals(1, count_logs(env, "probe\ttool=curl exit=launch"))
		assert.equals(1, #env.tasks)
	end)

	it("lands an OK verdict and stores its handshake RTT", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		complete_task(latest_task(env, "/usr/bin/curl"), 0, CURL_OK)

		local state = package.loaded.ping_window.parse_state(read_state_file(env))
		assert.same({ verdict = "ok", at = env.now, ms = 120 }, state.web)
		assert.is_nil(state.check)
		assert.equals(NBSP .. "✓ web" .. NBSP, title_text(env.menus[1].title))
		assert.is_true(read_events(env):find("\tweb\tverdict=ok ms=120 http=200 exit=0", 1, true) ~= nil)

		env.now = BobPingIndicator.webStartedAt + 10
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		complete_task(latest_task(env, "/usr/bin/curl"), 0, CURL_OK)
		local _, verdict_events = read_events(env):gsub("\tweb\t", "")
		assert.equals(1, verdict_events)
	end)

	it("lands portal and failed verdict details", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		complete_task(latest_task(env, "/usr/bin/curl"), 0, CURL_PORTAL)
		local portal = package.loaded.ping_window.parse_state(read_state_file(env))
		assert.equals("portal", portal.web.verdict)
		assert.is_nil(portal.check)
		local portal_rows = env.menus[1].menu_builder()
		local portal_row = nil
		for _, row in ipairs(portal_rows) do
			if item_title(row):find("Web check hit a sign-in page", 1, true) then
				portal_row = row
			end
		end
		assert.is_not_nil(portal_row)

		env.restore()
		env = nil
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		complete_task(latest_task(env, "/usr/bin/curl"), 6, "")
		local failed = package.loaded.ping_window.parse_state(read_state_file(env))
		assert.equals("fail", failed.web.verdict)
		assert.is_nil(failed.web.ms)
		assert.is_nil(failed.check)
		local rows = env.menus[1].menu_builder()
		local web_row = nil
		for _, row in ipairs(rows) do
			if item_title(row):find("Web check failed", 1, true) then
				web_row = row
			end
		end
		assert.is_not_nil(web_row)
		assert.is_true(item_title(web_row):find("DNS lookup failed", 1, true) ~= nil)
	end)

	it("clears the in-flight token without replacing a verdict for curl tool errors", function()
		local indicator
		env, indicator = setup()
		write_state_file(
			env,
			string.format("%d hammerspoon %d 0 web=fail,%d,-\n", env.now - 20, env.now - 20, env.now - 20)
		)
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		complete_task(latest_task(env, "/usr/bin/curl"), 127, "")
		local state = package.loaded.ping_window.parse_state(read_state_file(env))
		assert.same({ verdict = "fail", at = env.now - 20 }, state.web)
		assert.is_nil(state.check)
		assert.is_true(read_events(env):find("\tprobe\ttool=curl exit=127", 1, true) ~= nil)
		assert.is_nil(read_events(env):find("\tweb\t", 1, true))
	end)

	it("renders the ICMP-blind incident and slow-link web result without a pill", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d hammerspoon %d %s\n", env.now - 2, env.now - 2, string.rep("0", 29)))
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		assert.is_true(title_text(env.menus[1].title):find("✓ web", 1, true) == nil)
		for _, span in ipairs(title_spans(env.menus[1].title)) do
			assert.is_nil(span.attributes.backgroundColor)
		end
		complete_task(latest_task(env, "/usr/bin/curl"), 0, CURL_OK)
		assert.equals(NBSP .. "✓ web" .. NBSP, title_text(env.menus[1].title))

		env.restore()
		env = nil
		env, indicator = setup()
		write_state_file(env, string.format("%d hammerspoon %d 00\n", env.now - 4, env.now - 4))
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		assert.is_true(title_text(env.menus[1].title):find("✗", 1, true) ~= nil)
		for _, span in ipairs(title_spans(env.menus[1].title)) do
			assert.is_nil(span.attributes.backgroundColor)
		end
		complete_task(latest_task(env, "/usr/bin/curl"), 0, "Success\n__PING_WINDOW__ 200 0.010 2.110")
		assert.is_true(title_text(env.menus[1].title):find("✓", 1, true) ~= nil)
		assert.is_true(title_text(env.menus[1].title):find("2.1s", 1, true) ~= nil)
		for _, span in ipairs(title_spans(env.menus[1].title)) do
			assert.is_nil(span.attributes.backgroundColor)
		end
	end)

	it("walks healthy, ICMP-blind, outage, pill, and recovery states", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d hammerspoon %d %s\n", env.now - 2, env.now - 2, string.rep("1", 30)))
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(NBSP .. "✓" .. NBSP, title_text(env.menus[1].title))

		local curl_count = 0
		for missed = 1, 30 do
			env.now = env.now + 2
			fire_tick(env)
			complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
			local found = 0
			for _, task in ipairs(env.tasks) do
				if task.command == "/usr/bin/curl" then
					found = found + 1
				end
			end
			if found > curl_count then
				curl_count = found
				complete_task(latest_task(env, "/usr/bin/curl"), 0, CURL_OK)
			end
			if missed == 4 then
				assert.equals(NBSP .. "✓ web" .. NBSP, title_text(env.menus[1].title))
			end
		end
		assert.equals(NBSP .. "✓ web" .. NBSP, title_text(env.menus[1].title))

		env.now = BobPingIndicator.webStartedAt + 10
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		assert.equals(NBSP .. "✓ web" .. NBSP, title_text(env.menus[1].title))
		complete_task(latest_task(env, "/usr/bin/curl"), 28, "")
		assert.is_true(title_text(env.menus[1].title):find("✗", 1, true) ~= nil)
		assert.is_true(title_text(env.menus[1].title):find("0/30", 1, true) ~= nil)
		for _, span in ipairs(title_spans(env.menus[1].title)) do
			assert.same({ hex = "#E3413B", alpha = 1 }, span.attributes.backgroundColor)
		end

		for recovered = 1, 30 do
			env.now = env.now + 2
			fire_tick(env)
			complete_latest(env, 0, SUCCESS_TRANSCRIPT)
			if recovered == 1 then
				assert.is_true(title_text(env.menus[1].title):find("✓", 1, true) ~= nil)
			end
		end
		assert.equals(NBSP .. "✓" .. NBSP, title_text(env.menus[1].title))
		local events = read_events(env)
		assert.is_true(events:find("transition=online→web", 1, true) ~= nil)
		assert.is_true(events:find("\tweb\tverdict=ok", 1, true) ~= nil)
		assert.is_true(events:find("\tweb\tverdict=fail", 1, true) ~= nil)
		assert.is_true(events:find("transition=web→offline", 1, true) ~= nil)
		assert.is_true(events:find("transition=offline→lossy", 1, true) ~= nil)
		assert.is_true(events:find("transition=lossy→online", 1, true) ~= nil)
	end)

	it("keeps the offline pill until the web check fails and does not check while paused", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d hammerspoon %d 00\n", env.now - 4, env.now - 4))
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		for _, span in ipairs(title_spans(env.menus[1].title)) do
			assert.is_nil(span.attributes.backgroundColor)
		end
		complete_task(latest_task(env, "/usr/bin/curl"), 28, "")
		assert.is_true(title_text(env.menus[1].title):find("✗", 1, true) ~= nil)
		assert.is_true(title_text(env.menus[1].title):find("0/3", 1, true) ~= nil)
		for _, span in ipairs(title_spans(env.menus[1].title)) do
			assert.same({ hex = "#E3413B", alpha = 1 }, span.attributes.backgroundColor)
		end

		env.restore()
		env = nil
		env, indicator = setup({
			session_properties = { CGSSessionScreenIsLocked = true, kCGSSessionOnConsoleKey = true },
		})
		write_state_file(env, string.format("%d hammerspoon %d 00\n", env.now - 4, env.now - 4))
		start_indicator(env, indicator)
		assert.equals(0, #env.tasks)
		assert.is_nil(read_state_file(env):find("check=", 1, true))
	end)

	it("carries rtt, web, and check through paused and tmux heartbeat claims", function()
		local indicator
		env, indicator = setup({
			task_new_nil = true,
			session_properties = { CGSSessionScreenIsLocked = true, kCGSSessionOnConsoleKey = true },
		})
		start_indicator(env, indicator)
		local sample_at = env.now
		local web_at = env.now - 2
		write_state_file(
			env,
			string.format(
				"%d hammerspoon %d s0 rtt=480,1200 web=ok,%d,125 check=%d\n",
				env.now - 2,
				sample_at,
				web_at,
				web_at
			)
		)
		env.now = env.now + 2
		fire_tick(env)
		assert.equals(
			string.format(
				"%d hammerspoon %d s0 rtt=480,1200 web=ok,%d,125 check=%d\n",
				env.now,
				sample_at,
				web_at,
				web_at
			),
			read_state_file(env)
		)

		env.restore()
		env = nil
		env, indicator = setup({ task_new_nil = true })
		start_indicator(env, indicator)
		local tmux_at = env.now
		write_state_file(
			env,
			string.format("%d tmux %d s0 rtt=480,1200 web=ok,%d,125 check=%d\n", tmux_at, tmux_at, tmux_at, tmux_at)
		)
		fire_tick(env)
		assert.equals(
			string.format(
				"%d hammerspoon %d s0 rtt=480,1200 web=ok,%d,125 check=%d\n",
				env.now,
				tmux_at,
				tmux_at,
				tmux_at
			),
			read_state_file(env)
		)
	end)

	it("terminates an expired check and stops both tasks on reload", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local curl = latest_task(env, "/usr/bin/curl")
		env.now = env.now + 11
		fire_tick(env)
		assert.is_true(curl.terminated)
		assert.is_nil(read_state_file(env):find("check=", 1, true))
		assert.is_true(read_events(env):find("\tprobe\ttool=curl exit=grace", 1, true) ~= nil)

		env.restore()
		env = nil
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local active_curl = latest_task(env, "/usr/bin/curl")
		env.now = env.now + 2
		fire_tick(env)
		local active_ping = latest_task(env, "/sbin/ping")
		start_indicator(env, indicator)
		assert.is_true(active_curl.terminated)
		assert.is_true(active_ping.terminated)
		assert.is_true(read_state_file(env):find("check=", 1, true) == nil)
		assert.equals("/sbin/ping", latest_task(env, "/sbin/ping").command)
	end)

	it("logs start and tier transitions, trims at startup, and caps later growth", function()
		local indicator
		env, indicator = setup()
		write_events(env, package.loaded.ping_window.EVENTS_KEEP_LINES + 2)
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		local initial_lines = event_lines(env)
		assert.equals(package.loaded.ping_window.EVENTS_KEEP_LINES + 2, #initial_lines)
		assert.is_true(initial_lines[1]:find("old%-3\tseed") ~= nil)
		assert.is_true(initial_lines[1001]:find("\tstart\targs=", 1, true) ~= nil)
		assert.is_true(initial_lines[1001]:find("-n -q -c 1 -W 500 8.8.8.8", 1, true) ~= nil)
		assert.is_true(initial_lines[1002]:find("\ttier\ttransition=unknown→online", 1, true) ~= nil)
		assert.is_true(initial_lines[1002]:find("title=", 1, true) ~= nil)

		write_events(env, 2000)
		BobPingIndicator.eventLineCount = 2000
		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local capped_lines = event_lines(env)
		assert.equals(1000, #capped_lines)
		assert.equals("old-1002\tseed\tvalue=1002", capped_lines[1])
		assert.is_true(capped_lines[1000]:find("\ttier\ttransition=online→down", 1, true) ~= nil)
		assert.is_true(logged_message(env, "transition=online→down"))
	end)
end)

describe("Hammerspoon ping indicator dropdown", function()
	local env = nil

	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("builds the rows lazily in order and opens network settings", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		local menu = env.menus[1]
		assert.equals("function", type(menu.menu_builder))
		local items = menu.menu_builder()
		assert.equals(9, #items)

		assert.equals("✓ Online", item_title(items[1]))
		assert.is_true(items[1].disabled)
		assert.equals("●" .. string.rep("·", 29) .. "  now", item_title(items[2]))
		assert.is_true(items[2].disabled)
		assert.equals("1 of 1 pings answered (100%) · last 2 s", item_title(items[3]))
		assert.is_true(items[3].disabled)
		assert.equals("Last reply 18 ms · " .. os.date("%H:%M:%S", env.now), item_title(items[4]))
		assert.is_true(items[4].disabled)
		assert.equals("-", items[5].title)
		assert.equals(
			"Pinging 8.8.8.8 every 2 s · web check when pings fail · shared with tmux",
			item_title(items[6])
		)
		assert.is_true(items[6].disabled)
		assert.equals("-", items[7].title)
		assert.equals("Network Settings…", item_title(items[8]))
		assert.is_nil(items[8].disabled)
		assert.equals("function", type(items[8].fn))
		assert.equals("Copy Diagnostics", item_title(items[9]))
		assert.is_nil(items[9].disabled)
		assert.equals("function", type(items[9].fn))

		items[8].fn()
		assert.equals(1, #env.opened_bundle_urls)
		assert.equals(NETWORK_SETTINGS_URL, env.opened_bundle_urls[1].url)
		assert.equals(SYSTEM_SETTINGS_BUNDLE_ID, env.opened_bundle_urls[1].bundle)
		assert.equals(SYSTEM_SETTINGS_BUNDLE_ID, indicator.SYSTEM_SETTINGS_BUNDLE_ID)
		assert.equals(0, count_logs(env, "network settings failed"))
		assert.equals(0, #env.alerts)
	end)

	it("reports a false launch return with one log and one alert", function()
		local indicator
		env, indicator = setup({ open_bundle_result = false })
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		network_settings_item(env, indicator).fn()

		assert.equals(1, #env.opened_bundle_urls)
		assert.equals(1, count_logs(env, "network settings failed"))
		assert.is_true(logged_message(env, NETWORK_SETTINGS_URL))
		assert.equals(1, #env.alerts)
		assert.is_true(env.alerts[1]:find("Network Settings", 1, true) ~= nil)
	end)

	it("contains a launch exception with one log and one alert", function()
		local indicator
		env, indicator = setup({ open_bundle_throw = "launch boom" })
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		local item = network_settings_item(env, indicator)
		assert.has_no.errors(function()
			item.fn()
		end)

		assert.equals(1, #env.opened_bundle_urls)
		assert.equals(1, count_logs(env, "network settings failed"))
		assert.equals(1, #env.alerts)
		assert.is_true(env.alerts[1]:find("Network Settings", 1, true) ~= nil)
	end)

	it("recovers after a failed click and never retries from ticks", function()
		local indicator
		env, indicator = setup({ open_bundle_result = false })
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		local menu = env.menus[1]
		local builder = menu.menu_builder
		network_settings_item(env, indicator).fn()
		assert.equals(1, count_logs(env, "network settings failed"))
		assert.equals(1, #env.alerts)

		env.open_bundle_result = true
		env.open_bundle_throw = nil
		network_settings_item(env, indicator).fn()
		assert.equals(2, #env.opened_bundle_urls)
		assert.equals(1, count_logs(env, "network settings failed"))
		assert.equals(1, #env.alerts)

		local titles_before = #env.menu_titles
		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		assert.equals(2, #env.opened_bundle_urls)
		assert.equals(1, menu.set_menu_calls)
		assert.is_true(menu.menu_builder == builder)
		assert.is_true(#env.menu_titles > titles_before)
		assert.is_true(title_text(env.menus[1].title):find("2/2", 1, true) ~= nil)
	end)

	it("keeps one installed builder across ticks and ping completions so an open dropdown stays open", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		local menu = env.menus[1]
		local builder = menu.menu_builder
		assert.equals("function", type(builder))
		assert.equals(1, menu.set_menu_calls)
		local titles_before = #env.menu_titles

		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)

		assert.equals(1, menu.set_menu_calls)
		assert.is_true(menu.menu_builder == builder)
		assert.is_true(#env.menu_titles > titles_before)

		local items = builder()
		assert.equals("●●○" .. string.rep("·", 27) .. "  now", item_title(items[2]))
		assert.is_true(item_title(items[3]):find("2 of 3", 1, true) ~= nil)
	end)

	it("renders a 20-cell window when configured", function()
		local indicator
		env, indicator = setup()
		write_config_file(env, "window_size=20\n")
		write_state_file(env, string.format("%d tmux %d %s\n", env.now - 2, env.now - 2, string.rep("1", 20)))
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(
			string.format("%d hammerspoon %d %s rtt=18\n", env.now, env.now, string.rep("1", 20)),
			read_state_file(env)
		)
		local items = env.menus[1].menu_builder()
		assert.equals(string.rep("●", 20) .. "  now", item_title(items[2]))
		assert.equals(NBSP .. "✓" .. NBSP, title_text(env.menus[1].title))
	end)

	it("shows just the check mark for a perfect window and restores the count on a miss", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d tmux %d %s\n", env.now - 2, env.now - 2, string.rep("1", 29)))
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		assert.equals(NBSP .. "✓" .. NBSP, title_text(env.menus[1].title))
		local spans = assert(title_spans(env.menus[1].title))
		local glyph = assert(span_with_text(spans, "✓"))
		assert.are.same({ hex = "#30d158", alpha = 1 }, glyph.attributes.color)
		for _, span in ipairs(spans) do
			assert.is_nil(span.text:find("/", 1, true))
		end

		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		local miss_text = title_text(env.menus[1].title)
		assert.is_true(miss_text:find("✗", 1, true) ~= nil)
		assert.is_true(miss_text:find("29/30", 1, true) ~= nil)
		local miss_spans = assert(title_spans(env.menus[1].title))
		local miss_glyph = assert(span_with_text(miss_spans, "✗"))
		assert.are.same({ hex = "#E3413B", alpha = 1 }, miss_glyph.attributes.color)

		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		local recovered = title_text(env.menus[1].title)
		assert.is_true(recovered:find("✓", 1, true) ~= nil)
		assert.is_true(recovered:find("29/30", 1, true) ~= nil)
	end)

	it("falls back to just the check mark for a perfect window when styling fails", function()
		local indicator
		env, indicator = setup()
		env.fail_styling = true
		write_state_file(env, string.format("%d tmux %d %s\n", env.now - 2, env.now - 2, string.rep("1", 29)))
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)

		local title = env.menus[1].title
		assert.equals("string", type(title))
		assert.equals(NBSP .. "✓" .. NBSP, title)
	end)

	it("shrinks the window without a restart when the config changes", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d tmux %d %s\n", env.now - 2, env.now - 2, string.rep("1", 30)))
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(
			string.format("%d hammerspoon %d %s rtt=18\n", env.now, env.now, string.rep("1", 30)),
			read_state_file(env)
		)
		write_config_file(env, "window_size=20\n")
		env.now = env.now + 2
		fire_tick(env)
		assert.equals(2, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(
			string.format("%d hammerspoon %d %s rtt=18,18\n", env.now, env.now, string.rep("1", 20)),
			read_state_file(env)
		)
	end)

	it("logs an invalid config once and reuses the default", function()
		local indicator
		env, indicator = setup()
		write_config_file(env, "window_size=abc\n")
		write_state_file(env, string.format("%d tmux %d %s\n", env.now - 2, env.now - 2, string.rep("1", 20)))
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(1, count_logs(env, "invalid window_size"))
		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(1, count_logs(env, "invalid window_size"))
		assert.equals(
			string.format("%d hammerspoon %d %s rtt=18,18\n", env.now, env.now, string.rep("1", 22)),
			read_state_file(env)
		)
		write_config_file(env, "window_size=20\n")
		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(1, count_logs(env, "invalid window_size"))
		write_config_file(env, "window_size=xyz\n")
		env.now = env.now + 2
		fire_tick(env)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(2, count_logs(env, "invalid window_size"))
	end)
end)

describe("Hammerspoon slow and web title styles", function()
	local env
	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("styles a slow glyph amber with a padded Menlo latency", function()
		local indicator
		env, indicator = setup({ task_new_nil = true })
		local state = string.format("%d hammerspoon %d sss rtt=1200,1400,1600\n", env.now, env.now)
		write_state_file(env, state)
		start_indicator(env, indicator)
		local title = env.menus[1].title
		assert.equals(NBSP .. "✓ " .. FIGURE_SPACE .. "1.4s" .. NBSP, title_text(title))
		local spans = title_spans(title)
		assert.same({ hex = "#FF9F0A", alpha = 1 }, span_with_text(spans, "✓").attributes.color)
		local latency = span_with_text(spans, "1.4s").attributes
		assert.equals("Menlo-Regular", latency.font.name)
		assert.same({ list = "System", name = "labelColor", alpha = 1 }, latency.color)
		assert.is_nil(latency.backgroundColor)
		assert.equals(state, read_state_file(env))
	end)

	it("styles web green with an unpadded secondary note in the menu bar font", function()
		local indicator
		env, indicator = setup({ task_new_nil = true })
		local state = string.format("%d hammerspoon %d 000 web=ok,%d,120\n", env.now, env.now, env.now)
		write_state_file(env, state)
		start_indicator(env, indicator)
		local title = env.menus[1].title
		assert.equals(NBSP .. "✓ web" .. NBSP, title_text(title))
		local spans = title_spans(title)
		assert.same({ hex = "#30d158", alpha = 1 }, span_with_text(spans, "✓").attributes.color)
		local note = span_with_text(spans, "web").attributes
		assert.equals(".AppleSystemUIFont", note.font.name)
		assert.same({ list = "System", name = "secondaryLabelColor", alpha = 1 }, note.color)
		assert.is_nil(note.backgroundColor)
		assert.equals(state, read_state_file(env))
	end)
end)

local function has_menu_item(items, title)
	for _, item in ipairs(items) do
		if item_title(item) == title then
			return true
		end
	end
	return false
end

describe("Hammerspoon ping dropdown styling, diagnostics, and preview", function()
	local env
	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("colors the header glyph and history strip by role", function()
		local indicator
		env, indicator = setup({ task_new_nil = true })
		write_state_file(env, string.format("%d hammerspoon %d 1s0\n", env.now, env.now))
		start_indicator(env, indicator)
		local items = env.menus[1].menu_builder()
		local header = title_spans(items[1].title)
		assert.same({ hex = "#E3413B", alpha = 1 }, span_with_text(header, "✗").attributes.color)
		assert.equals(".AppleSystemUIFont", header[1].attributes.font.name)
		local strip = title_spans(items[2].title)
		assert.equals("●◐○" .. string.rep("·", 27) .. "  now", item_title(items[2]))
		assert.same({ hex = "#30d158", alpha = 1 }, strip[1].attributes.color)
		assert.same({ hex = "#FF9F0A", alpha = 1 }, strip[2].attributes.color)
		assert.same({ list = "System", name = "secondaryLabelColor", alpha = 1 }, strip[3].attributes.color)
		assert.same({ list = "System", name = "tertiaryLabelColor", alpha = 1 }, strip[4].attributes.color)
		assert.same({ list = "System", name = "secondaryLabelColor", alpha = 1 }, strip[#strip].attributes.color)
		assert.equals(".AppleSystemUIFont", strip[1].attributes.font.name)
		assert.equals(".AppleSystemUIFont", strip[#strip].attributes.font.name)
	end)

	it("falls back to plain row text when styling throws", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		env.fail_styling = true
		local items = env.menus[1].menu_builder()
		assert.equals("string", type(items[1].title))
		assert.equals("✓ Online", items[1].title)
		assert.equals("string", type(items[2].title))
		assert.equals("●" .. string.rep("·", 29) .. "  now", items[2].title)
		assert.equals("string", type(items[9].title))
		assert.equals("Copy Diagnostics", items[9].title)
		assert.equals("function", type(items[9].fn))
	end)

	it("copies a diagnostics report with state, ping, web, and recent events", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 2, TIMEOUT_TRANSCRIPT)
		complete_task(latest_task(env, "/usr/bin/curl"), 0, CURL_OK)
		write_events(env, 25)
		copy_diagnostics_item(env).fn()
		assert.equals(1, #env.pasteboard_writes)
		local report = env.pasteboard_writes[1]
		assert.is_true(report:find("Ping diagnostics · ", 1, true) ~= nil)
		assert.is_true(report:find("tier: web", 1, true) ~= nil)
		assert.is_true(report:find("title: ✓ web", 1, true) ~= nil)
		assert.is_true(report:find("header: ✓ Online · pings unanswered", 1, true) ~= nil)
		assert.is_true(report:find("state: " .. read_state_file(env):gsub("\n$", ""), 1, true) ~= nil)
		assert.is_true(report:find("ping: /sbin/ping -n -q -c 1 -W 500 8.8.8.8", 1, true) ~= nil)
		assert.is_true(report:find("last ping: exit=2 rtt=-", 1, true) ~= nil)
		assert.is_true(report:find("web: ok at=" .. tostring(env.now) .. " ms=120", 1, true) ~= nil)
		assert.is_true(
			report:find("web detail: at=" .. tostring(env.now) .. " reason=- http=200 exit=0", 1, true) ~= nil
		)
		assert.is_nil(report:find("old-5\t", 1, true))
		assert.is_true(report:find("old-6\tseed\tvalue=6", 1, true) ~= nil)
		assert.is_true(report:find("old-25\tseed\tvalue=25", 1, true) ~= nil)
		assert.equals("Ping diagnostics copied", env.alerts[#env.alerts])
		assert.equals(1.5, env.alert_calls[#env.alert_calls].duration)
		assert.equals(0, count_logs(env, "copy diagnostics failed"))
	end)

	it("logs and alerts when the pasteboard rejects diagnostics", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		env.pasteboard_false = true
		assert.has_no.errors(function()
			copy_diagnostics_item(env).fn()
		end)
		assert.equals(0, #env.pasteboard_writes)
		assert.equals(1, count_logs(env, "copy diagnostics failed"))
		assert.equals("Ping diagnostics could not be copied", env.alerts[#env.alerts])
	end)

	it("shows Preview All States only while option is held", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.is_false(has_menu_item(env.menus[1].menu_builder(), "Preview All States"))
		assert.is_true(has_menu_item(env.menus[1].menu_builder({ alt = true }), "Preview All States"))
		env.held_modifiers = { alt = true }
		assert.is_true(has_menu_item(env.menus[1].menu_builder(), "Preview All States"))
	end)

	it("steps titles on a 2.5 s timer, skips live setTitle, and never writes", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		local menu = env.menus[1]
		local builder = menu.menu_builder
		local set_menu_calls = menu.set_menu_calls
		local state_before = read_state_file(env)
		local events_before = read_events(env)
		find_menu_item(menu.menu_builder({ alt = true }), "Preview All States").fn()
		assert.equals(state_before, read_state_file(env))
		assert.equals(events_before, read_events(env))
		assert.equals(1, #env.do_after)
		assert.equals(indicator.PREVIEW_STEP_SECONDS, env.do_after[1].delay)
		assert.equals("Preview · perfect", env.alerts[#env.alerts])
		assert.equals(2, env.alert_calls[#env.alert_calls].duration)
		assert.equals(NBSP .. "✓" .. NBSP, title_text(menu.title))
		local preview_title = menu.title
		env.now = env.now + 2
		fire_tick(env)
		assert.equals(preview_title, menu.title)
		assert.equals(state_before, read_state_file(env))
		local labels = {
			"count",
			"slow",
			"web",
			"lossy",
			"down/checking",
			"offline",
			"offline/portal",
			"stale",
		}
		for _, label in ipairs(labels) do
			fire_do_after(env)
			assert.equals("Preview · " .. label, env.alerts[#env.alerts])
			assert.equals(state_before, read_state_file(env))
			assert.equals(events_before, read_events(env))
		end
		assert.is_true(title_text(menu.title):find("◌", 1, true) ~= nil)
		fire_do_after(env)
		assert.is_false(BobPingIndicator.previewing)
		assert.equals(state_before, read_state_file(env))
		assert.equals(events_before, read_events(env))
		assert.is_true(title_text(menu.title):find("✓", 1, true) ~= nil)
		assert.is_true(title_text(menu.title):find("1/1", 1, true) ~= nil)
		assert.equals(set_menu_calls, menu.set_menu_calls)
		assert.is_true(menu.menu_builder == builder)
	end)

	it("cancels an in-flight preview when start runs again", function()
		local indicator
		env, indicator = setup()
		start_indicator(env, indicator)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		find_menu_item(env.menus[1].menu_builder({ alt = true }), "Preview All States").fn()
		local preview_timer = env.do_after[1]
		assert.is_true(BobPingIndicator.previewing)
		start_indicator(env, indicator)
		assert.is_false(BobPingIndicator.previewing)
		assert.equals(1, preview_timer.stop_calls)
		assert.is_nil(BobPingIndicator.previewTimer)
	end)
end)
