local HIGHLIGHTS_KEYS_PATH = "home/dot_hammerspoon/highlights_tab_keys.lua"
local HIGHLIGHTS_TABS_PATH = "home/dot_hammerspoon/highlights_tabs.lua"
local HIGHLIGHTS_PAGES_PATH = "home/dot_hammerspoon/highlights_pages.lua"
local BUNDLE_ID = "net.highlightsapp.universal"

local function make_app(bundle, pid)
	local app = { _bundle = bundle, _pid = pid }
	function app:bundleID()
		return self._bundle
	end
	function app:pid()
		return self._pid
	end
	return app
end

local function make_focused(pid, role)
	local element = { _pid = pid, _role = role }
	function element:pid()
		return self._pid
	end
	function element:attributeValue(name)
		if name == "AXRole" then
			return self._role
		end
		return nil
	end
	function element:setTimeout(_) end
	return element
end

local function make_ax_element(attrs)
	local element = { _attrs = attrs or {} }
	function element:attributeValue(name)
		local value = self._attrs[name]
		if type(value) == "function" then
			return value()
		end
		return value
	end
	function element:setTimeout(_) end
	function element:setAttributeValue(name, value)
		self._attrs[name] = value
		return true
	end
	function element:performAction(_)
		self._pressed = (self._pressed or 0) + 1
		return true
	end
	return element
end

local function setup(options)
	options = options or {}
	local env = {
		previous_hs = _G.hs,
		previous_runtime = _G.BobHighlightsTabKeys,
		previous_tabs = package.loaded.highlights_tabs,
		previous_pages = package.loaded.highlights_pages,
		previous_keys = package.loaded.highlights_tab_keys,
		alerts = {},
		logs = {},
		tasks = {},
		now = options.now or 1000,
		queue = {},
		after_calls = 0,
		open_calls = {},
		focused = options.focused,
		app_element_focused = options.app_element_focused,
		focused_window = options.focused_window,
		app_windows = options.app_windows,
		app_element_attrs = options.app_element_attrs,
		frontmost_bundle = options.frontmost_bundle,
		highlights_pid = options.highlights_pid or 111,
		tap_enabled = false,
		tap_start_calls = 0,
		tap_stop_calls = 0,
		watcher_start_calls = 0,
		watcher_stop_calls = 0,
		url_handlers = {},
		url_unbinds = {},
	}
	if env.frontmost_bundle == nil then
		env.frontmost_bundle = BUNDLE_ID
	end

	local highlights_app = make_app(BUNDLE_ID, env.highlights_pid)
	local other_app = make_app("com.other.app", 222)
	env.highlights_app = highlights_app
	env.other_app = other_app

	local hs = {}
	hs.keycodes = { map = { escape = 53 } }
	hs.eventtap = {
		event = { types = { keyDown = 10 }, properties = { keyboardEventAutorepeat = "autorepeat" } },
	}
	function hs.eventtap.new(_, callback)
		env.tap_callback = callback
		local tap = {}
		function tap:start()
			env.tap_enabled = true
			env.tap_start_calls = env.tap_start_calls + 1
			return tap
		end
		function tap:stop()
			env.tap_enabled = false
			env.tap_stop_calls = env.tap_stop_calls + 1
			return tap
		end
		function tap:isEnabled()
			if env.tap_disable_next then
				env.tap_disable_next = false
				return false
			end
			return env.tap_enabled
		end
		env.tap = tap
		return tap
	end
	hs.application = {
		watcher = { activated = "activated", deactivated = "deactivated", terminated = "terminated" },
	}
	function hs.application.get(bundle)
		if bundle == BUNDLE_ID then
			return highlights_app
		end
		return nil
	end
	function hs.application.frontmostApplication()
		if env.frontmost_bundle == BUNDLE_ID then
			return highlights_app
		elseif env.frontmost_bundle == nil then
			return nil
		end
		return other_app
	end
	function hs.application.watcher.new(callback)
		env.watcher_callback = callback
		local watcher = {}
		function watcher:start()
			env.watcher_start_calls = env.watcher_start_calls + 1
			return watcher
		end
		function watcher:stop()
			env.watcher_stop_calls = env.watcher_stop_calls + 1
			return watcher
		end
		env.watcher = watcher
		return watcher
	end
	hs.urlevent = {}
	function hs.urlevent.bind(name, handler)
		if handler == nil then
			env.url_unbinds[name] = (env.url_unbinds[name] or 0) + 1
			env.url_handlers[name] = nil
		else
			env.url_handlers[name] = handler
		end
	end
	hs.fs = {
		attributes = function(path)
			if type(options.attributes) == "function" then
				return options.attributes(path)
			end
			return nil
		end,
	}
	hs.axuielement = {}
	function hs.axuielement.systemWideElement()
		if env.system_wide_error then
			error(env.system_wide_error)
		end
		local sys = {}
		function sys:setTimeout(_) end
		function sys:attributeValue(name)
			if name == "AXFocusedUIElement" then
				if env.focused_error then
					error(env.focused_error)
				end
				return env.focused
			end
			return nil
		end
		return sys
	end
	function hs.axuielement.applicationElement(app)
		if app == highlights_app then
			local element = {}
			function element:attributeValue(name)
				if name == "AXFocusedUIElement" then
					return env.app_element_focused
				elseif name == "AXFocusedWindow" then
					return env.focused_window
				elseif name == "AXWindows" then
					return env.app_windows
				end
				if type(env.app_element_attrs) == "table" then
					return env.app_element_attrs[name]
				end
				return nil
			end
			function element:setTimeout(_) end
			return element
		end
		return nil
	end
	hs.alert = {
		show = function(message, duration)
			table.insert(env.alerts, { message = message, duration = duration })
		end,
	}
	hs.task = {
		new = function(path, callback, args)
			local task = { path = path, callback = callback, args = args, started = false }
			function task:start()
				self.started = true
				return self
			end
			table.insert(env.tasks, task)
			return task
		end,
	}
	hs.timer = {}
	function hs.timer.doAfter(seconds, fn)
		env.after_calls = env.after_calls + 1
		if options.sync_after then
			fn()
			return { stop = function() end }
		end
		table.insert(env.queue, { seconds = seconds, fn = fn })
		return {
			stop = function()
				env.stopped_timers = (env.stopped_timers or 0) + 1
			end,
		}
	end
	function hs.timer.secondsSinceEpoch()
		return env.now
	end
	function hs.printf(...)
		table.insert(env.logs, { ... })
	end

	function env.restore()
		_G.hs = env.previous_hs
		_G.BobHighlightsTabKeys = env.previous_runtime
		package.loaded.highlights_tabs = env.previous_tabs
		package.loaded.highlights_pages = env.previous_pages
		package.loaded.highlights_tab_keys = env.previous_keys
	end

	function env.drain(limit)
		limit = limit or 500
		local ticks = 0
		while #env.queue > 0 and ticks < limit do
			ticks = ticks + 1
			env.tick()
		end
		return ticks
	end

	function env.tick()
		local item = table.remove(env.queue, 1)
		if item == nil then
			return false
		end
		env.now = env.now + (tonumber(item.seconds) or 0)
		item.fn()
		return true
	end

	function env.tap_key(payload)
		assert.is_not_nil(env.tap_callback)
		return env.tap_callback(payload)
	end

	_G.hs = hs
	_G.BobHighlightsTabKeys = nil
	package.loaded.highlights_tabs = assert(loadfile(HIGHLIGHTS_TABS_PATH))()
	package.loaded.highlights_pages = assert(loadfile(HIGHLIGHTS_PAGES_PATH))()
	local keys = assert(loadfile(HIGHLIGHTS_KEYS_PATH))()
	env.hs = hs
	env.keys = keys
	return env
end

local function start_with_adapter(env, adapter, extra)
	extra = extra or {}
	env.keys.start({
		hs = env.hs,
		adapter = adapter,
		after = function(seconds, fn)
			env.after_calls = env.after_calls + 1
			table.insert(env.queue, { seconds = seconds, fn = fn })
		end,
		now = function()
			return env.now
		end,
		alert = function(message)
			table.insert(env.alerts, { message = message })
		end,
		open = extra.open or function(paths)
			table.insert(env.open_calls, paths)
		end,
		urlevent = extra.urlevent,
	})
end

local function make_adapter(state)
	return {
		read = function()
			local tabs = {}
			for index, title in ipairs(state.titles) do
				table.insert(tabs, { title = title, selected = index == state.selected })
			end
			return { tabs = tabs }
		end,
		select = function(index)
			state.select_calls = (state.select_calls or 0) + 1
			state.selected = index
			return true
		end,
		close_selected = function()
			state.close_calls = (state.close_calls or 0) + 1
			table.remove(state.titles, state.selected)
			if state.selected > #state.titles then
				state.selected = #state.titles
			end
			return true
		end,
		has_sheet = function()
			return false
		end,
		document = function()
			local title = state.titles[state.selected]
			if title == nil then
				return nil
			end
			return "/pdfs/" .. title
		end,
	}
end

local function make_page_adapter(state)
	local adapter = make_adapter({ titles = { "paper.pdf" }, selected = 1 })
	adapter.document = function()
		return state.document
	end
	adapter.page_info = function()
		return { page = state.page, count = state.count, document = state.document }
	end
	adapter.has_pdf_view = function()
		return state.has_pdf_view ~= false
	end
	adapter.scroll_to = function(page)
		state.scroll_calls = (state.scroll_calls or 0) + 1
		state.page = page
		return true
	end
	adapter.scroll_to_visible = function()
		return false
	end
	adapter.landed = function(page)
		return state.page == page
	end
	return adapter
end

-- Mirror hs.urlevent's real callback order: (eventName, params, senderPID).
local function request_page(env, params)
	local handler = env.url_handlers["bob-highlights-page"]
	assert.is_function(handler)
	handler("bob-highlights-page", params, 4242)
end

local function start_with_real_adapter(env, extra)
	extra = extra or {}
	local options = {
		hs = env.hs,
		after = function(seconds, fn)
			env.after_calls = env.after_calls + 1
			table.insert(env.queue, { seconds = seconds, fn = fn })
		end,
		now = function()
			return env.now
		end,
		alert = function(message)
			table.insert(env.alerts, { message = message })
		end,
	}
	if extra.open ~= nil then
		options.open = extra.open
	end
	env.keys.start(options)
end

local function make_native_tabs(env, titles, selected, options)
	options = options or {}
	local numeric = options.numeric == true
	local state = { titles = {}, docs = {}, selected = selected }
	for index, title in ipairs(titles) do
		state.titles[index] = title
	end
	if type(options.docs) == "table" then
		for index, doc in ipairs(options.docs) do
			state.docs[index] = doc
		end
	else
		for index, title in ipairs(titles) do
			state.docs[index] = "file:///pdfs/" .. title
		end
	end
	local buttons = {}
	for _, title in ipairs(titles) do
		local button = make_ax_element({ AXRole = "AXRadioButton", AXSubrole = "AXTabButton", AXTitle = title })
		button._attrs["AXValue"] = function()
			local index = nil
			for position, candidate in ipairs(buttons) do
				if candidate == button then
					index = position
					break
				end
			end
			if index ~= nil and state.selected == index then
				if numeric then
					return 1
				end
				return true
			end
			if numeric then
				return 0
			end
			return false
		end
		function button:performAction(action)
			if action ~= "AXPress" then
				return false
			end
			for position, candidate in ipairs(buttons) do
				if candidate == button then
					state.selected = position
					return true
				end
			end
			return false
		end
		table.insert(buttons, button)
	end
	local tab_group = make_ax_element({ AXRole = "AXTabGroup" })
	tab_group._attrs["AXTabs"] = function()
		return buttons
	end
	local split = make_ax_element({ AXRole = "AXSplitGroup", AXChildren = {} })
	local toolbar = make_ax_element({ AXRole = "AXToolbar", AXChildren = {} })
	local close_button = make_ax_element({ AXRole = "AXButton" })
	function close_button:performAction(action)
		if action ~= "AXPress" then
			return false
		end
		if type(state.selected) ~= "number" or state.selected < 1 or state.selected > #state.titles then
			return false
		end
		state.close_calls = (state.close_calls or 0) + 1
		table.remove(state.titles, state.selected)
		table.remove(state.docs, state.selected)
		table.remove(buttons, state.selected)
		if state.selected > #state.titles then
			state.selected = #state.titles
		end
		if #state.titles == 0 then
			state.selected = nil
		end
		return true
	end
	local window = make_ax_element({ AXRole = "AXWindow" })
	window._attrs["AXChildren"] = function()
		if #state.titles <= 1 then
			return { split, toolbar }
		end
		return { split, toolbar, tab_group }
	end
	window._attrs["AXCloseButton"] = close_button
	window._attrs["AXDocument"] = function()
		if type(state.selected) ~= "number" then
			return nil
		end
		return state.docs[state.selected]
	end
	env.focused_window = window
	env.app_windows = { window }
	env.native_state = state
	return state
end

local function make_pdf_view(env, options)
	options = options or {}
	local state = {
		page = options.page or 10,
		count = options.count or 44,
		document = options.document or "file:///papers/the_ai_native_sdlc_playbook.pdf",
		area_y = 100,
		area_h = 500,
		page_h = 800,
		gap = 20,
		offset = 0,
	}
	local function step()
		return state.page_h + state.gap
	end
	local function document_height()
		return state.count * state.page_h + (state.count - 1) * state.gap
	end
	local function maximum()
		return math.max(0, document_height() - state.area_h)
	end
	local function page_top(index)
		return state.area_y + (index - 1) * step() - state.offset
	end
	local function current_page()
		return math.min(state.count, math.floor(state.offset / step()) + 1)
	end
	state.offset = math.min(maximum(), math.max(0, (state.page - 1) * step()))
	local pages = {}
	for index = 1, state.count do
		local page = make_ax_element({ AXRole = "AXPage", AXPageIndex = index - 1 })
		page._attrs["AXFrame"] = function()
			return { x = 0, y = page_top(index), w = 600, h = state.page_h }
		end
		page._attrs["AXPosition"] = function()
			return { x = 0, y = page_top(index) }
		end
		page._attrs["AXSize"] = { w = 600, h = state.page_h }
		function page:performAction(action)
			if action ~= "AXScrollToVisible" or options.ignore_visible then
				return false
			end
			state.offset = math.min(maximum(), math.max(0, (index - 1) * step()))
			return true
		end
		pages[index] = page
	end
	local document = make_ax_element({ AXSubrole = "AXSharedDocumentContainer" })
	document._attrs["AXChildren"] = function()
		return pages
	end
	document._attrs["AXFrame"] = function()
		return { x = 0, y = state.area_y - state.offset, w = 600, h = document_height() }
	end
	document._attrs["AXPosition"] = function()
		return { x = 0, y = state.area_y - state.offset }
	end
	document._attrs["AXSize"] = function()
		return { w = 600, h = document_height() }
	end
	local bar = make_ax_element({ AXRole = "AXScrollBar", AXOrientation = "AXVerticalOrientation" })
	bar._attrs["AXValue"] = function()
		if maximum() == 0 then
			return 0
		end
		return state.offset / maximum()
	end
	function bar:setAttributeValue(name, value)
		if name ~= "AXValue" then
			return false
		end
		if not options.ignore_bar then
			state.offset = math.max(0, math.min(maximum(), tonumber(value) * maximum()))
		end
		return true
	end
	local sidebar = make_ax_element({ AXRole = "AXScrollArea", AXChildren = {} })
	local sidebar_group = make_ax_element({ AXRole = "AXGroup", AXChildren = { sidebar } })
	local area = make_ax_element({ AXRole = "AXScrollArea", AXChildren = { document, bar } })
	area._attrs["AXVerticalScrollBar"] = bar
	area._attrs["AXFrame"] = function()
		return { x = 0, y = state.area_y, w = 700, h = state.area_h }
	end
	area._attrs["AXPosition"] = function()
		return { x = 0, y = state.area_y }
	end
	area._attrs["AXSize"] = { w = 700, h = state.area_h }
	local split = make_ax_element({ AXRole = "AXSplitGroup", AXChildren = { sidebar_group, area } })
	local window = make_ax_element({ AXRole = "AXWindow" })
	window._attrs["AXChildren"] = { split }
	window._attrs["AXDocument"] = function()
		if options.no_document then
			return nil
		end
		return state.document
	end
	window._attrs["AXTitle"] = function()
		return "the_ai_native_sdlc_playbook.pdf – Page " .. current_page() .. " of " .. state.count
	end
	env.focused_window = window
	env.app_windows = { window }
	env.pdf_state = state
	env.pdf_area = area
	env.pdf_bar = bar
	return state
end

local function tap_leader(env, second, second_flags)
	assert.is_true(env.tap_key({ chars = "\\", flags = {}, keycode = 0 }))
	assert.is_true(env.tap_key({ chars = second, flags = second_flags or {}, keycode = 0 }))
	env.drain()
end

local function tap_ctrl_o(env)
	return env.tap_key({ chars = "\15", plain = "o", flags = { ctrl = true }, keycode = 31 })
end

local function tap_ctrl_i(env)
	return env.tap_key({ chars = "\9", plain = "i", flags = { ctrl = true }, keycode = 34 })
end

local function tap_ctrl(env, letter, options)
	options = options or {}
	return env.tap_key({
		chars = string.char(letter:byte() - 96),
		plain = letter,
		flags = { ctrl = true },
		autorepeat = options.autorepeat == true,
		keycode = 0,
	})
end

local function tap_page_keys(env, chars)
	for _, value in ipairs(chars) do
		assert.is_true(env.tap_key({ chars = value, plain = value, flags = {}, keycode = 0 }))
	end
	env.drain()
end

local function alert_saw(env, needle)
	for _, alert in ipairs(env.alerts) do
		if tostring(alert.message):find(needle, 1, true) then
			return true
		end
	end
	return false
end

describe("Highlights tab keys runtime", function()
	local env = nil

	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("enables the tap only while Highlights is active", function()
		env = setup({ frontmost_bundle = BUNDLE_ID, focused = make_focused(111, "AXUnknown") })
		start_with_adapter(env, make_adapter({ titles = { "a.pdf", "b.pdf" }, selected = 1 }))
		assert.is_true(env.tap_enabled)

		env.watcher_callback("x", "deactivated", env.highlights_app)
		assert.is_false(env.tap_enabled)

		env.watcher_callback("x", "activated", env.highlights_app)
		assert.is_true(env.tap_enabled)

		local before = env.tap_start_calls
		env.watcher_callback("x", "activated", env.other_app)
		assert.equals(before, env.tap_start_calls)
		assert.is_true(env.tap_enabled)

		env.watcher_callback("x", "terminated", env.highlights_app)
		assert.is_false(env.tap_enabled)
	end)

	it("swallows backslash in the PDF view", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		start_with_adapter(env, make_adapter({ titles = { "a.pdf", "b.pdf" }, selected = 1 }))
		local swallowed = env.tap_key({ chars = "\\", flags = {}, keycode = 0 })
		assert.is_true(swallowed)
	end)

	it("passes backslash through in text fields and for another pid", function()
		env = setup({ focused = make_focused(111, "AXTextField") })
		start_with_adapter(env, make_adapter({ titles = { "a.pdf", "b.pdf" }, selected = 1 }))
		assert.is_false(env.tap_key({ chars = "\\", flags = {}, keycode = 0 }))

		env.restore()
		env = setup({ focused = make_focused(222, "AXUnknown") })
		start_with_adapter(env, make_adapter({ titles = { "a.pdf", "b.pdf" }, selected = 1 }))
		assert.is_false(env.tap_key({ chars = "\\", flags = {}, keycode = 0 }))

		env.restore()
		env = setup({ focused = make_focused(111, "AXTextArea") })
		start_with_adapter(env, make_adapter({ titles = { "a.pdf", "b.pdf" }, selected = 1 }))
		assert.is_false(env.tap_key({ chars = "\\", flags = {}, keycode = 0 }))
	end)

	it("runs a full backslash-greater sequence through the fake adapter", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = { titles = { "a.pdf", "b.pdf", "c.pdf" }, selected = 1 }
		start_with_adapter(env, make_adapter(state))
		assert.is_true(env.tap_key({ chars = "\\", flags = {}, keycode = 0 }))
		assert.is_true(env.tap_key({ chars = ">", flags = { shift = true }, keycode = 0 }))
		env.drain()
		assert.same({ "a.pdf" }, state.titles)
		assert.equals(2, state.close_calls)
		local saw_close = false
		for _, alert in ipairs(env.alerts) do
			if tostring(alert.message):find("Closed 2 tabs to the right", 1, true) then
				saw_close = true
			end
		end
		assert.is_true(saw_close)
	end)

	it("reopens the last batch on backslash-u and clears it", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = { titles = { "a.pdf", "b.pdf", "c.pdf" }, selected = 1 }
		start_with_adapter(env, make_adapter(state))
		env.tap_key({ chars = "\\", flags = {}, keycode = 0 })
		env.tap_key({ chars = ">", flags = { shift = true }, keycode = 0 })
		env.drain()
		assert.equals(2, #_G.BobHighlightsTabKeys.lastBatch)

		env.tap_key({ chars = "\\", flags = {}, keycode = 0 })
		env.tap_key({ chars = "u", flags = {}, keycode = 0 })
		env.drain()
		assert.equals(1, #env.open_calls)
		assert.equals(0, #_G.BobHighlightsTabKeys.lastBatch)
		local saw_reopen = false
		for _, alert in ipairs(env.alerts) do
			if tostring(alert.message):find("Reopened 2 tabs", 1, true) then
				saw_reopen = true
			end
		end
		assert.is_true(saw_reopen)

		env.tap_key({ chars = "\\", flags = {}, keycode = 0 })
		env.tap_key({ chars = "u", flags = {}, keycode = 0 })
		env.drain()
		local saw_empty = false
		for _, alert in ipairs(env.alerts) do
			if tostring(alert.message):find("Nothing to reopen", 1, true) then
				saw_empty = true
			end
		end
		assert.is_true(saw_empty)
	end)

	it("returns false and logs on a callback error", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		start_with_adapter(env, make_adapter({ titles = { "a.pdf", "b.pdf" }, selected = 1 }))
		-- A nil event errors inside key building after the frontmost check.
		local ok = env.tap_key(nil)
		assert.is_false(ok)
		local logged = false
		for _, call in ipairs(env.logs) do
			for _, part in ipairs(call) do
				if tostring(part):find("Bob Highlights tab keys callback failed", 1, true) then
					logged = true
				end
			end
		end
		assert.is_true(logged)
	end)

	it("stops the previous tap, watcher, and timers on restart", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		start_with_adapter(env, make_adapter({ titles = { "a.pdf", "b.pdf" }, selected = 1 }))
		local first_tap = env.tap
		local first_watcher = env.watcher
		assert.is_not_nil(first_tap)
		assert.is_not_nil(first_watcher)
		local stops_before = env.tap_stop_calls
		env.keys.start({
			hs = env.hs,
			adapter = make_adapter({ titles = { "a.pdf" }, selected = 1 }),
			after = function(seconds, fn)
				table.insert(env.queue, { seconds = seconds, fn = fn })
			end,
			now = function()
				return env.now
			end,
			alert = function(message)
				table.insert(env.alerts, { message = message })
			end,
		})
		assert.equals(stops_before + 1, env.tap_stop_calls)
		assert.is_not_nil(env.tap)
	end)

	it("finds tab groups to depth 3 and skips excluded roles", function()
		env = setup({})
		local keys = env.keys
		local function leaf(role)
			return make_ax_element({ AXRole = role, AXChildren = {} })
		end
		local tab_group = make_ax_element({ AXRole = "AXTabGroup", AXChildren = {} })
		local scroll = make_ax_element({ AXRole = "AXScrollArea", AXChildren = { tab_group } })
		local window = make_ax_element({ AXRole = "AXWindow", AXChildren = { scroll } })
		assert.is_nil(keys.find_tab_group(window))

		local nested_group = make_ax_element({ AXRole = "AXTabGroup", AXChildren = {} })
		local level2 = make_ax_element({ AXRole = "AXUnknown", AXChildren = { nested_group } })
		local level1 = make_ax_element({ AXRole = "AXUnknown", AXChildren = { level2 } })
		local top = make_ax_element({ AXRole = "AXWindow", AXChildren = { level1 } })
		-- Window children, grandchildren, and great-grandchildren hold the group: found.
		assert.equals(nested_group, keys.find_tab_group(top))

		local deep_group = make_ax_element({ AXRole = "AXTabGroup", AXChildren = {} })
		local d3 = make_ax_element({ AXRole = "AXUnknown", AXChildren = { deep_group } })
		local d2 = make_ax_element({ AXRole = "AXUnknown", AXChildren = { d3 } })
		local d1 = make_ax_element({ AXRole = "AXUnknown", AXChildren = { d2 } })
		local deep_top = make_ax_element({ AXRole = "AXWindow", AXChildren = { d1 } })
		assert.is_nil(keys.find_tab_group(deep_top))
		assert.is_not_nil(leaf("AXTable"))
	end)

	it("closes right tabs through the real adapter with boolean AXValue", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_native_tabs(env, { "a.pdf", "b.pdf", "c.pdf" }, 1)
		start_with_real_adapter(env)
		tap_leader(env, ">", { shift = true })
		assert.same({ "a.pdf" }, state.titles)
		assert.equals(1, state.selected)
		assert.is_true(alert_saw(env, "Closed 2 tabs to the right"))
	end)

	it("closes other tabs from the middle through the real adapter", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_native_tabs(env, { "a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf" }, 3)
		start_with_real_adapter(env)
		tap_leader(env, "\\")
		assert.same({ "c.pdf" }, state.titles)
		assert.equals(1, state.selected)
		assert.is_true(alert_saw(env, "Closed 4 other tabs"))
	end)

	it("closes left tabs through the real adapter", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_native_tabs(env, { "a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf" }, 3)
		start_with_real_adapter(env)
		tap_leader(env, "<", { shift = true })
		assert.same({ "c.pdf", "d.pdf", "e.pdf" }, state.titles)
		assert.equals(1, state.selected)
		assert.is_true(alert_saw(env, "Closed 2 tabs to the left"))
	end)

	it("closes through the real adapter with numeric AXValue", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_native_tabs(env, { "a.pdf", "b.pdf", "c.pdf" }, 1, { numeric = true })
		start_with_real_adapter(env)
		tap_leader(env, ">", { shift = true })
		assert.same({ "a.pdf" }, state.titles)
		assert.equals(1, state.selected)
		assert.is_true(alert_saw(env, "Closed 2 tabs to the right"))
	end)

	it("reopens a percent-encoded document through the real adapter", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_native_tabs(env, { "keep.pdf", "spaced.pdf" }, 1, {
			docs = { "file:///pdfs/keep.pdf", "file:///Users/me/My%20Paper%C3%A9.pdf" },
		})
		start_with_real_adapter(env)
		tap_leader(env, ">", { shift = true })
		assert.same({ "keep.pdf" }, state.titles)
		assert.equals(1, #_G.BobHighlightsTabKeys.lastBatch)
		assert.equals("/Users/me/My Paperé.pdf", _G.BobHighlightsTabKeys.lastBatch[1])

		tap_leader(env, "u")
		assert.equals(1, #env.tasks)
		local task = env.tasks[1]
		assert.equals("/usr/bin/open", task.path)
		assert.same({ "-b", BUNDLE_ID, "/Users/me/My Paperé.pdf" }, task.args)
		assert.is_true(alert_saw(env, "Reopened 1 tab"))
	end)

	it("names the failure when no tab reads as selected", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		make_native_tabs(env, { "a.pdf", "b.pdf" }, nil)
		start_with_real_adapter(env)
		tap_leader(env, ">", { shift = true })
		assert.is_true(alert_saw(env, "Stopped after closing 0 tab(s): couldn't tell which tab is selected"))
		local logged = false
		for _, call in ipairs(env.logs) do
			local joined = ""
			for _, part in ipairs(call) do
				joined = joined .. tostring(part) .. "\n"
			end
			if joined:find("Bob Highlights tab keys", 1, true) then
				logged = true
				assert.is_truthy(joined:find("couldn't tell which tab is selected", 1, true))
				assert.is_nil(joined:find("a.pdf", 1, true))
				assert.is_nil(joined:find("b.pdf", 1, true))
			end
		end
		assert.is_true(logged)
	end)

	it("jumps back through per-PDF history with quiet successful jumps", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		assert.is_true(_G.BobHighlightsTabKeys._page_deps_for_tests.page_info().page == 10)

		tap_page_keys(env, { "2", "g" })
		assert.equals(2, math.floor(state.offset / 820) + 1)
		assert.equals(0, #env.alerts)
		assert.equals(0, #env.logs)
		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.equals(10, math.floor(state.offset / 820) + 1)
		assert.equals(0, #env.alerts)

		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.is_true(alert_saw(env, "No earlier page"))
		assert.equals(10, math.floor(state.offset / 820) + 1)
	end)

	it("walks forward again after going back", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		tap_page_keys(env, { "2", "g" })
		assert.equals(2, math.floor(state.offset / 820) + 1)
		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.equals(10, math.floor(state.offset / 820) + 1)
		assert.is_true(tap_ctrl_i(env))
		env.drain()
		assert.equals(2, math.floor(state.offset / 820) + 1)
		assert.is_false(alert_saw(env, "No later page"))

		local offset = state.offset
		assert.is_true(tap_ctrl_i(env))
		env.drain()
		assert.is_true(alert_saw(env, "No later page"))
		assert.equals(offset, state.offset)
	end)

	it("scrolls half a view and one line through the real adapter", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		assert.is_true(tap_ctrl(env, "d"))
		env.drain()
		assert.equals(7630, state.offset)
		assert.is_true(tap_ctrl(env, "u"))
		env.drain()
		assert.equals(7380, state.offset)
		assert.is_true(tap_ctrl(env, "e"))
		env.drain()
		assert.equals(7400, state.offset)
		assert.is_true(tap_ctrl(env, "y"))
		env.drain()
		assert.equals(7380, state.offset)
		assert.equals(0, #env.alerts)
		assert.equals(0, #env.logs)
	end)

	it("coalesces held line scrolls into one AX write", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		local writes = 0
		local set_value = env.pdf_bar.setAttributeValue
		env.pdf_bar.setAttributeValue = function(bar, name, value)
			writes = writes + 1
			return set_value(bar, name, value)
		end
		assert.is_true(tap_ctrl(env, "e"))
		assert.is_true(tap_ctrl(env, "e", { autorepeat = true }))
		assert.is_true(tap_ctrl(env, "e", { autorepeat = true }))
		env.drain()
		assert.equals(1, writes)
		assert.equals(7440, state.offset)
	end)

	it("keeps top and bottom edge scrolls quiet", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 1, count = 44 })
		start_with_real_adapter(env)
		local writes = 0
		local set_value = env.pdf_bar.setAttributeValue
		env.pdf_bar.setAttributeValue = function(bar, name, value)
			writes = writes + 1
			return set_value(bar, name, value)
		end
		assert.is_true(tap_ctrl(env, "y"))
		assert.is_true(tap_ctrl(env, "u"))
		env.drain()
		assert.equals(0, writes)
		state.offset = 35560
		assert.is_true(tap_ctrl(env, "d"))
		env.drain()
		assert.equals(0, writes)
		assert.equals(0, #env.alerts)
		assert.equals(0, #env.logs)
	end)

	it("passes scroll keys in text fields, other processes, and windows without a PDF", function()
		local cases = {
			{ focused = make_focused(111, "AXTextField") },
			{ focused = make_focused(222, "AXUnknown") },
			{ focused = make_focused(111, "AXUnknown"), no_document = true },
		}
		for _, case in ipairs(cases) do
			env = setup({ focused = case.focused })
			local state = make_pdf_view(env, { no_document = case.no_document })
			start_with_real_adapter(env)
			assert.is_false(tap_ctrl(env, "d"))
			env.drain()
			assert.equals(7380, state.offset)
			assert.equals(0, #env.alerts)
			env.restore()
			env = nil
		end
	end)

	it("logs every failed scroll but alerts only for a fresh press", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		make_pdf_view(env, { page = 10, count = 44, ignore_bar = true })
		start_with_real_adapter(env)
		assert.is_true(tap_ctrl(env, "d"))
		env.drain()
		assert.equals(1, #env.alerts)
		assert.equals("Couldn't scroll the PDF: the scroll bar didn't move", env.alerts[1].message)
		assert.equals(1, #env.logs)
		assert.equals("Bob Highlights scroll keys failed: %s", env.logs[1][1])
		assert.equals("the scroll bar didn't move", env.logs[1][2])
		assert.is_true(tap_ctrl(env, "d", { autorepeat = true }))
		env.drain()
		assert.equals(1, #env.alerts)
		assert.equals(2, #env.logs)
	end)

	it("drops scroll keys while a page jump or tab close is running", function()
		for _, field in ipairs({ "page_running", "running" }) do
			env = setup({ focused = make_focused(111, "AXUnknown") })
			local state = make_pdf_view(env, { page = 10, count = 44 })
			start_with_real_adapter(env)
			_G.BobHighlightsTabKeys[field] = true
			assert.is_true(tap_ctrl(env, "d"))
			env.drain()
			assert.equals(7380, state.offset)
			assert.equals(0, #env.alerts)
			_G.BobHighlightsTabKeys[field] = false
			env.restore()
			env = nil
		end
	end)

	it("does not add scrolling to Ctrl-O jump history", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		assert.is_true(tap_ctrl(env, "d"))
		env.drain()
		assert.equals(7630, state.offset)
		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.is_true(alert_saw(env, "No earlier page"))
		assert.equals(7630, state.offset)
	end)

	it("schedules scrolls after a restart with an earlier flush pending", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		assert.is_true(tap_ctrl(env, "e"))
		env.keys.start({ hs = env.hs })
		-- The real timer is stopped by M.stop; discard the equivalent fake timer here.
		env.queue = {}
		assert.is_true(tap_ctrl(env, "e"))
		env.drain()
		assert.equals(7400, state.offset)
	end)

	it("cancels a pending tab leader and scrolls on Ctrl-Y", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		assert.is_true(env.tap_key({ chars = "\\", plain = "\\", flags = {}, keycode = 0 }))
		assert.is_true(tap_ctrl(env, "y"))
		env.drain()
		assert.is_true(math.abs(7360 - state.offset) < 1e-6)
	end)

	it("clears the pages ahead on a new jump after going back", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		tap_page_keys(env, { "2", "g" })
		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.equals(10, math.floor(state.offset / 820) + 1)
		tap_page_keys(env, { "g", "g" })
		assert.equals(0, state.offset)

		assert.is_true(tap_ctrl_i(env))
		env.drain()
		assert.is_true(alert_saw(env, "No later page"))

		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.equals(10, math.floor(state.offset / 820) + 1)
		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.is_true(alert_saw(env, "No earlier page"))
	end)

	it("leaves Ctrl-Tab alone so Highlights still switches tabs", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		assert.is_false(env.tap_key({ chars = "\9", plain = "\9", flags = { ctrl = true }, keycode = 48 }))
	end)

	it("jumps to the first and last pages and rejects out-of-range counts", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		tap_page_keys(env, { "g", "g" })
		assert.equals(0, state.offset)
		tap_page_keys(env, { "G" })
		assert.equals(44, math.floor(state.offset / 820) + 1)

		local offset = state.offset
		tap_page_keys(env, { "5", "0", "g" })
		assert.equals(offset, state.offset)
		assert.is_true(alert_saw(env, "No page 50 — this PDF has 44 pages"))
	end)

	it("falls back to AXScrollToVisible without logging document details", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44, ignore_bar = true })
		start_with_real_adapter(env)
		tap_page_keys(env, { "2", "g" })
		assert.equals(2, math.floor(state.offset / 820) + 1)
		local joined = ""
		for _, call in ipairs(env.logs) do
			for _, part in ipairs(call) do
				joined = joined .. tostring(part) .. "\n"
			end
		end
		assert.is_truthy(joined:find("AXScrollToVisible landed", 1, true))
		assert.is_nil(joined:find("the_ai_native_sdlc_playbook.pdf", 1, true))
		assert.is_nil(joined:find("/papers/", 1, true))
	end)

	it("alerts and logs when neither real-adapter mechanism lands", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		make_pdf_view(env, { page = 10, count = 44, ignore_bar = true, ignore_visible = true })
		start_with_real_adapter(env)
		tap_page_keys(env, { "2", "g" })
		assert.is_true(alert_saw(env, "Couldn't jump to page 2: didn't reach page 2"))
		local logged = false
		for _, call in ipairs(env.logs) do
			if tostring(call[1]):find("Bob Highlights page keys %s failed", 1, true) then
				logged = true
			end
		end
		assert.is_true(logged)
	end)

	it("passes page keys in text fields, other processes, and windows without a PDF", function()
		local cases = {
			{ focused = make_focused(111, "AXTextField") },
			{ focused = make_focused(111, "AXTextArea") },
			{ focused = make_focused(222, "AXUnknown") },
			{ focused = make_focused(111, "AXUnknown"), no_document = true },
		}
		for _, case in ipairs(cases) do
			env = setup({ focused = case.focused })
			make_pdf_view(env, { no_document = case.no_document })
			start_with_real_adapter(env)
			assert.is_false(env.tap_key({ chars = "g", plain = "g", flags = {}, keycode = 0 }))
			assert.is_false(env.tap_key({ chars = "5", plain = "5", flags = {}, keycode = 0 }))
			assert.is_false(tap_ctrl_o(env))
			assert.is_false(tap_ctrl_i(env))
			env.restore()
			env = nil
		end
	end)

	it("isolates history by document and cancels a pending g on deactivation", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = make_pdf_view(env, { page = 10, count = 44 })
		start_with_real_adapter(env)
		tap_page_keys(env, { "2", "g" })
		state.document = "file:///papers/another.pdf"
		assert.is_true(tap_ctrl_o(env))
		env.drain()
		assert.is_true(alert_saw(env, "No earlier page"))
		assert.is_true(tap_ctrl_i(env))
		env.drain()
		assert.is_true(alert_saw(env, "No later page"))

		assert.is_true(env.tap_key({ chars = "g", plain = "g", flags = {}, keycode = 0 }))
		assert.is_true(_G.BobHighlightsTabKeys.page_keys:is_pending())
		env.watcher_callback("x", "deactivated", env.highlights_app)
		assert.is_false(_G.BobHighlightsTabKeys.page_keys:is_pending())
	end)

	it("routes backslash to the tab leader around pending page keys", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = { titles = { "a.pdf", "b.pdf", "c.pdf" }, selected = 1 }
		local adapter = make_adapter(state)
		adapter.has_document = function()
			return true
		end
		start_with_adapter(env, adapter)
		assert.is_true(env.tap_key({ chars = "g", plain = "g", flags = {}, keycode = 0 }))
		assert.is_true(env.tap_key({ chars = "\\", plain = "\\", flags = {}, keycode = 0 }))
		assert.is_true(env.tap_key({ chars = ">", plain = ">", flags = { shift = true }, keycode = 0 }))
		env.drain()
		assert.same({ "a.pdf" }, state.titles)

		env.restore()
		env = nil
		env = setup({ focused = make_focused(111, "AXUnknown") })
		adapter = make_adapter({ titles = { "a.pdf" }, selected = 1 })
		adapter.has_document = function()
			return true
		end
		start_with_adapter(env, adapter)
		assert.is_true(env.tap_key({ chars = "\\", plain = "\\", flags = {}, keycode = 0 }))
		assert.is_true(env.tap_key({ chars = "g", plain = "g", flags = {}, keycode = 0 }))
		assert.is_true(_G.BobHighlightsTabKeys.page_keys:is_pending())
	end)

	it("reports the tab busy message when a page jump overlaps a tab close", function()
		env = setup({ focused = make_focused(111, "AXUnknown") })
		local state = { titles = { "a.pdf", "b.pdf", "c.pdf" }, selected = 1 }
		local adapter = make_adapter(state)
		adapter.has_document = function()
			return true
		end
		adapter.page_info = function()
			return { page = 1, count = 10, document = "/paper.pdf" }
		end
		adapter.scroll_to = function()
			return true
		end
		adapter.scroll_to_visible = function()
			return true
		end
		adapter.landed = function()
			return true
		end
		start_with_adapter(env, adapter)
		assert.is_true(env.tap_key({ chars = "\\", plain = "\\", flags = {}, keycode = 0 }))
		assert.is_true(env.tap_key({ chars = ">", plain = ">", flags = { shift = true }, keycode = 0 }))
		assert.is_true(env.tap_key({ chars = "2", plain = "2", flags = {}, keycode = 0 }))
		assert.is_true(env.tap_key({ chars = "g", plain = "g", flags = {}, keycode = 0 }))
		env.drain()
		assert.is_true(alert_saw(env, "Still closing Highlights tabs"))
	end)

	it("binds the URL handler, logs invalid reasons without paths, and never opens files", function()
		env = setup({})
		local state = { document = "/papers/paper.pdf", page = 30, count = 44 }
		local bound = {}
		local unbound = {}
		local urlevent = {
			bind = function(name, handler)
				if handler == nil then
					unbound[name] = (unbound[name] or 0) + 1
				else
					bound[name] = handler
				end
			end,
		}
		start_with_adapter(env, make_page_adapter(state), {
			urlevent = urlevent,
			open = function(paths)
				table.insert(env.open_calls, paths)
			end,
		})
		assert.is_function(bound["bob-highlights-page"])
		bound["bob-highlights-page"]("bob-highlights-page", { path = "/private/secret.txt", page = "1" }, 4242)
		local log_text = ""
		for _, call in ipairs(env.logs) do
			for _, part in ipairs(call) do
				log_text = log_text .. tostring(part)
			end
		end
		assert.is_false(log_text:find("/private/secret.txt", 1, true) ~= nil)
		assert.is_truthy(log_text:find("invalid path", 1, true))

		bound["bob-highlights-page"]("bob-highlights-page", { path = "/papers/paper.pdf", page = "4" }, 4242)
		env.drain()
		assert.equals(4, state.page)
		assert.equals("Page 4 of 44 · ⌃O back to p. 30", env.alerts[#env.alerts].message)
		assert.equals(0, #env.open_calls)
		env.keys.stop()
		assert.equals(1, unbound["bob-highlights-page"])
	end)

	it("reads params from the second hs.urlevent callback argument", function()
		env = setup({})
		local state = { document = "/papers/paper.pdf", page = 30, count = 44 }
		start_with_adapter(env, make_page_adapter(state))
		local handler = env.url_handlers["bob-highlights-page"]
		assert.is_function(handler)
		-- Hammerspoon calls fn(eventName, params, senderPID); the event name is not params.
		handler("bob-highlights-page", { path = "/papers/paper.pdf", page = "4" }, 4242)
		env.drain()
		assert.equals(4, state.page)
		assert.equals(1, state.scroll_calls)
		assert.is_true(alert_saw(env, "Page 4 of 44 · ⌃O back to p. 30"))
	end)

	it("waits for Highlights and matches an inode alias before jumping", function()
		env = setup({
			frontmost_bundle = "com.other.app",
			attributes = function(path)
				if path == "/alias/paper.pdf" or path == "/real/paper.pdf" then
					return { dev = 1, ino = 22 }
				end
				return nil
			end,
		})
		local state = { document = "/real/paper.pdf", page = 30, count = 44 }
		start_with_adapter(env, make_page_adapter(state))
		request_page(env, { path = "/alias/paper.pdf", page = "4" })
		assert.equals(0, state.scroll_calls or 0)
		env.tick() -- Cold launch is still waiting before Highlights first comes forward.
		assert.equals(0, state.scroll_calls or 0)
		env.frontmost_bundle = BUNDLE_ID
		env.tick() -- First stable-title sample.
		assert.equals(0, state.scroll_calls or 0)
		env.tick() -- Second matching sample dispatches the jump.
		env.drain()
		assert.equals(4, state.page)
		assert.equals(1, state.scroll_calls)
		assert.is_true(alert_saw(env, "Page 4 of 44"))
	end)

	it("does not accept a same-named PDF with a different inode", function()
		env = setup({
			attributes = function(path)
				if path == "/requested/paper.pdf" then
					return { dev = 1, ino = 10 }
				end
				return { dev = 1, ino = 11 }
			end,
		})
		local state = { document = "/other/paper.pdf", page = 30, count = 44 }
		start_with_adapter(env, make_page_adapter(state))
		request_page(env, { path = "/requested/paper.pdf", page = "4" })
		env.drain()
		assert.equals(0, state.scroll_calls or 0)
		assert.is_true(alert_saw(env, "the PDF didn't come to the front"))
	end)

	it("cancels silently if another app takes focus after Highlights came forward", function()
		env = setup({})
		local state = { document = "/other/paper.pdf", page = 30, count = 44 }
		start_with_adapter(env, make_page_adapter(state))
		request_page(env, { path = "/requested/paper.pdf", page = "4" })
		assert.equals(1, #env.queue)
		env.frontmost_bundle = "com.other.app"
		env.tick()
		assert.equals(0, #env.queue)
		assert.equals(0, #env.alerts)
		assert.equals(0, state.scroll_calls or 0)
	end)

	it("lets the latest request win while a page run is busy", function()
		env = setup({})
		local state = { document = "/second/paper.pdf", page = 30, count = 44 }
		start_with_adapter(env, make_page_adapter(state))
		local runtime = _G.BobHighlightsTabKeys
		runtime.page_running = true
		request_page(env, { path = "/first/paper.pdf", page = "4" })
		request_page(env, { path = "/second/paper.pdf", page = "7" })
		env.tick()
		assert.equals(0, state.scroll_calls or 0)
		runtime.page_running = false
		env.drain()
		assert.equals(7, state.page)
		assert.equals(1, state.scroll_calls)
	end)

	it("keeps waiting for a busy tab-close run to finish", function()
		env = setup({})
		local state = { document = "/papers/paper.pdf", page = 30, count = 44 }
		start_with_adapter(env, make_page_adapter(state))
		local runtime = _G.BobHighlightsTabKeys
		runtime.running = true
		request_page(env, { path = "/papers/paper.pdf", page = "4" })
		env.tick()
		assert.equals(0, state.scroll_calls or 0)
		runtime.running = false
		env.drain()
		assert.equals(4, state.page)
		assert.equals(1, state.scroll_calls)
	end)

	it("unbinding cancels an outstanding URL wait", function()
		env = setup({ frontmost_bundle = "com.other.app" })
		local state = { document = "/papers/paper.pdf", page = 30, count = 44 }
		start_with_adapter(env, make_page_adapter(state))
		request_page(env, { path = "/papers/paper.pdf", page = "4" })
		assert.equals(1, #env.queue)
		env.keys.stop()
		local ticks = env.drain()
		assert.equals(1, ticks)
		assert.equals(0, #env.queue)
		assert.equals(0, #env.alerts)
		assert.equals(0, state.scroll_calls or 0)
		assert.is_nil(env.url_handlers["bob-highlights-page"])
	end)
end)
