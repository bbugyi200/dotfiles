local PING_WINDOW_PATH = "home/dot_hammerspoon/ping_window.lua"
local PING_INDICATOR_PATH = "home/dot_hammerspoon/ping_indicator.lua"

local NBSP = "\194\160" -- U+00A0
local FIGURE_SPACE = "\226\128\135" -- U+2007

local PING_ARGS = { "-n", "-q", "-c", "1", "-t", "1", "8.8.8.8" }
local NETWORK_SETTINGS_URL = "x-apple.systempreferences:com.apple.Network-Settings.extension"

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
		self.started = true
		self.start_calls = self.start_calls + 1
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
			if env.task_new_nil then
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
	}

	hs.menubar = {
		new = function(in_menu_bar, autosave_name)
			local menu = {
				in_menu_bar = in_menu_bar,
				autosave_name = autosave_name,
				title = nil,
				tooltip = nil,
				menu_builder = nil,
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
		openURL = function(url)
			table.insert(env.opened_urls, url)
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
		menus = {},
		menu_titles = {},
		printf_calls = {},
		styled_text_calls = {},
		styled_compositions = {},
		convert_font_calls = {},
		valid_font_calls = {},
		opened_urls = {},
		fs_attribute_calls = {},
		mkdir_calls = {},
		now = options.now or 1759680002,
		state_path = tmp_base .. "_ping_state",
		session_properties = options.session_properties,
		session_throw = options.session_throw,
		task_new_nil = options.task_new_nil,
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
		ping_path = "/sbin/ping",
		now = env.now_fn,
	})
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

		assert.equals(string.format("%d hammerspoon %d 1\n", env.now, env.now), read_state_file(env))

		local text = title_text(env.menus[1].title)
		assert.equals(NBSP .. "✓" .. " " .. FIGURE_SPACE .. FIGURE_SPACE .. "1/1" .. NBSP, text)

		local spans = assert(title_spans(env.menus[1].title))
		local glyph = assert(span_with_text(spans, "✓"))
		assert.are.same({ hex = "#30d158", alpha = 1 }, glyph.attributes.color)
		local count = assert(span_with_text(spans, "1/1"))
		assert.equals("Menlo-Regular", count.attributes.font.name)
		assert.are.same({ list = "System", name = "labelColor", alpha = 1 }, count.attributes.color)

		assert.equals("Internet: 1 of 1 pings answered (100%) · last reply 18 ms", env.menus[1].tooltip)
	end)

	it("paints a red failure and escalates to the pill after three misses", function()
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

		assert.equals(string.format("%d hammerspoon %d 000\n", env.now, env.now), read_state_file(env))
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
		assert.equals(string.format("%d hammerspoon %d 01111\n", env.now, env.now), read_state_file(env))
	end)

	it("resets the window after a long gap", function()
		local indicator
		env, indicator = setup()
		write_state_file(env, string.format("%d tmux %d 0111\n", env.now - 41, env.now - 41))
		start_indicator(env, indicator)
		assert.equals(1, #env.tasks)
		complete_latest(env, 0, SUCCESS_TRANSCRIPT)
		assert.equals(string.format("%d hammerspoon %d 1\n", env.now, env.now), read_state_file(env))
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

		start_indicator(env, indicator)

		assert.equals(1, old_timer.stop_calls)
		assert.is_true(old_task.terminated)
		assert.equals(1, #env.menus)
		assert.equals(old_menu, env.menus[1])
		assert.equals(2, #env.timers)
		assert.is_true(env.timers[2].started)
		assert.equals(2, #env.tasks)
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
		assert.equals(8, #items)

		assert.equals("✓ Online", items[1].title)
		assert.is_true(items[1].disabled)
		assert.equals("●" .. string.rep("·", 19) .. "  now", items[2].title)
		assert.is_true(items[2].disabled)
		assert.equals("1 of 1 pings answered (100%) · last 2 s", items[3].title)
		assert.is_true(items[3].disabled)
		assert.equals("Last reply 18 ms · " .. os.date("%H:%M:%S", env.now), items[4].title)
		assert.is_true(items[4].disabled)
		assert.equals("-", items[5].title)
		assert.equals("Pinging 8.8.8.8 every 2 s · shared with tmux", items[6].title)
		assert.is_true(items[6].disabled)
		assert.equals("-", items[7].title)
		assert.equals("Network Settings…", items[8].title)
		assert.is_nil(items[8].disabled)
		assert.equals("function", type(items[8].fn))

		items[8].fn()
		assert.same({ NETWORK_SETTINGS_URL }, env.opened_urls)
	end)
end)
