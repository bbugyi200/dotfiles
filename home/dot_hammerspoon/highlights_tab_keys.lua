-- Hammerspoon Highlights tab-close leader keys runtime (hs glue).
-- The pure leader, runner, and alert copy live in `highlights_tabs.lua`; this
-- module only wires `hs` event taps, watchers, and Accessibility to it.
local HighlightsTabs = require("highlights_tabs")

local M = {}

M.BUNDLE_ID = HighlightsTabs.BUNDLE_ID

if type(BobHighlightsTabKeys) ~= "table" then
	BobHighlightsTabKeys = {}
end

local runtime = BobHighlightsTabKeys

local AX_TIMEOUT_SECONDS = 0.4
local AX_FOCUS_TIMEOUT_SECONDS = 0.25

local EXCLUDED_ROLES = {
	AXScrollArea = true,
	AXWebArea = true,
	AXTextArea = true,
	AXTable = true,
	AXOutline = true,
}

local function ax_attr(element, name)
	if element == nil then
		return nil
	end
	if type(element.setTimeout) == "function" then
		pcall(function()
			element:setTimeout(AX_TIMEOUT_SECONDS)
		end)
	end
	if type(element.attributeValue) == "function" then
		local ok, value = pcall(function()
			return element:attributeValue(name)
		end)
		if ok then
			return value
		end
		return nil
	end
	if type(element) == "table" then
		return element[name]
	end
	return nil
end

local function ax_press(element)
	if element == nil then
		return false
	end
	if type(element.performAction) == "function" then
		local ok, result = pcall(function()
			return element:performAction("AXPress")
		end)
		if ok then
			return result ~= false
		end
		return false
	end
	return false
end

--- Search `AXChildren` from a window to a depth of at most 3 for `AXTabGroup`.
--- Never descends into scroll, web, text, table, or outline roles.
function M.find_tab_group(window, depth)
	depth = depth or 0
	if window == nil or depth >= 3 then
		return nil
	end
	local children = ax_attr(window, "AXChildren")
	if type(children) ~= "table" then
		return nil
	end
	for _, child in ipairs(children) do
		if type(child) == "table" or type(child) == "userdata" then
			local role = ax_attr(child, "AXRole")
			if role == "AXTabGroup" then
				return child
			end
			if role == nil or not EXCLUDED_ROLES[role] then
				local found = M.find_tab_group(child, depth + 1)
				if found ~= nil then
					return found
				end
			end
		end
	end
	return nil
end

local function frontmost_bundle_id(H)
	if H == nil or H.application == nil or type(H.application.frontmostApplication) ~= "function" then
		return nil
	end
	local ok, app = pcall(function()
		return H.application.frontmostApplication()
	end)
	if not ok or app == nil then
		return nil
	end
	if type(app.bundleID) == "function" then
		local ok_bid, bid = pcall(function()
			return app:bundleID()
		end)
		if ok_bid then
			return bid
		end
		return nil
	end
	if type(app.bundleID) == "string" then
		return app.bundleID
	end
	return nil
end

local function highlights_app(H)
	if H == nil or H.application == nil then
		return nil
	end
	if type(H.application.get) == "function" then
		local ok, app = pcall(function()
			return H.application.get(M.BUNDLE_ID)
		end)
		if ok and app ~= nil then
			return app
		end
	end
	if type(H.application.frontmostApplication) == "function" then
		local ok, app = pcall(function()
			return H.application.frontmostApplication()
		end)
		if ok and app ~= nil then
			local bid = nil
			if type(app.bundleID) == "function" then
				local ok_bid, value = pcall(function()
					return app:bundleID()
				end)
				if ok_bid then
					bid = value
				end
			elseif type(app.bundleID) == "string" then
				bid = app.bundleID
			end
			if bid == M.BUNDLE_ID then
				return app
			end
		end
	end
	return nil
end

local function highlights_app_element(H)
	local app = highlights_app(H)
	if app == nil or H.axuielement == nil then
		return nil
	end
	if type(H.axuielement.applicationElement) == "function" then
		local ok, element = pcall(function()
			return H.axuielement.applicationElement(app)
		end)
		if ok and element ~= nil then
			return element
		end
	end
	return nil
end

local function highlights_pid(H)
	local app = highlights_app(H)
	if app == nil then
		return nil
	end
	if type(app.pid) == "function" then
		local ok, pid = pcall(function()
			return app:pid()
		end)
		if ok and type(pid) == "number" then
			return pid
		end
		return nil
	end
	if type(app.pid) == "number" then
		return app.pid
	end
	return nil
end

local function focused_pid_and_role(H)
	local ax = H.axuielement
	if ax == nil or type(ax.systemWideElement) ~= "function" then
		return nil, nil, false
	end
	local ok_sys, sys = pcall(function()
		return ax.systemWideElement()
	end)
	if not ok_sys or sys == nil then
		return nil, nil, false
	end
	if type(sys.setTimeout) == "function" then
		pcall(function()
			sys:setTimeout(AX_FOCUS_TIMEOUT_SECONDS)
		end)
	end
	local focused = nil
	if type(sys.attributeValue) == "function" then
		local ok_focus, value = pcall(function()
			return sys:attributeValue("AXFocusedUIElement")
		end)
		if ok_focus then
			focused = value
		end
	end
	if focused == nil then
		local app_element = highlights_app_element(H)
		if app_element ~= nil and type(app_element.attributeValue) == "function" then
			local ok_focus, value = pcall(function()
				return app_element:attributeValue("AXFocusedUIElement")
			end)
			if ok_focus then
				focused = value
			end
		end
		if focused == nil then
			return nil, nil, true
		end
	end
	local pid = nil
	if type(focused.pid) == "function" then
		local ok_pid, value = pcall(function()
			return focused:pid()
		end)
		if ok_pid and type(value) == "number" then
			pid = value
		end
	elseif type(focused.pid) == "number" then
		pid = focused.pid
	end
	local role = nil
	if type(focused.attributeValue) == "function" then
		local ok_role, value = pcall(function()
			return focused:attributeValue("AXRole")
		end)
		if ok_role then
			role = value
		end
	elseif type(focused) == "table" then
		role = focused.AXRole
	end
	return pid, role, true
end

local function make_can_arm(H)
	return function()
		local ok, result = pcall(function()
			local pid, role, readable = focused_pid_and_role(H)
			if not readable then
				return true
			end
			local hpid = highlights_pid(H)
			if type(pid) == "number" and type(hpid) == "number" and pid ~= hpid then
				return false
			end
			if role == "AXTextField" or role == "AXTextArea" or role == "AXComboBox" then
				return false
			end
			return true
		end)
		if not ok then
			return true
		end
		return result
	end
end

local function doc_to_path(value)
	if type(value) ~= "string" or value == "" then
		return nil
	end
	if value:sub(1, 7) == "file://" then
		local path = value:gsub("^file://[^/]*", "")
		path = path:gsub("^localhost", "")
		if path == "" or path:sub(1, 1) ~= "/" then
			return nil
		end
		return path
	end
	if value:sub(1, 1) == "/" then
		return value
	end
	return nil
end

local function make_real_adapter(H)
	local function focused_window()
		local app_element = highlights_app_element(H)
		if app_element == nil then
			return nil
		end
		return ax_attr(app_element, "AXFocusedWindow")
	end

	local function read()
		if highlights_app(H) == nil then
			return nil, "Highlights is not running"
		end
		local app_element = highlights_app_element(H)
		if app_element == nil then
			return nil, "couldn't read Highlights' tabs"
		end
		local window = ax_attr(app_element, "AXFocusedWindow")
		if window == nil then
			return nil, "couldn't read Highlights' window"
		end
		local group = M.find_tab_group(window)
		if group == nil then
			return { tabs = nil }
		end
		local raw = ax_attr(group, "AXTabs")
		if type(raw) ~= "table" or #raw == 0 then
			return { tabs = nil }
		end
		local tabs = {}
		for _, button in ipairs(raw) do
			local title = ax_attr(button, "AXTitle")
			if type(title) ~= "string" or title == "" then
				title = "Untitled"
			end
			local raw_value = ax_attr(button, "AXValue")
			local selected = raw_value == 1 or tonumber(raw_value) == 1
			table.insert(tabs, { title = title, selected = selected == true })
		end
		return { tabs = tabs }
	end

	local function select(index)
		local window = focused_window()
		if window == nil then
			return false
		end
		local group = M.find_tab_group(window)
		if group == nil then
			return false
		end
		local raw = ax_attr(group, "AXTabs")
		if type(raw) ~= "table" then
			return false
		end
		local button = raw[index]
		if button == nil then
			return false
		end
		return ax_press(button)
	end

	local function close_selected()
		local window = focused_window()
		if window == nil then
			return false
		end
		local current = focused_window()
		if current ~= nil then
			window = current
		end
		local close_button = ax_attr(window, "AXCloseButton")
		if close_button == nil then
			return false
		end
		return ax_press(close_button)
	end

	local function window_has_sheet(window)
		if window == nil then
			return false
		end
		local children = ax_attr(window, "AXChildren")
		if type(children) ~= "table" then
			return false
		end
		for _, child in ipairs(children) do
			if ax_attr(child, "AXRole") == "AXSheet" then
				return true
			end
		end
		return false
	end

	local function has_sheet()
		local ok, result = pcall(function()
			local window = focused_window()
			if window_has_sheet(window) then
				return true
			end
			local app_element = highlights_app_element(H)
			if app_element == nil then
				return false
			end
			local windows = ax_attr(app_element, "AXWindows")
			if type(windows) ~= "table" then
				return false
			end
			for _, window_item in ipairs(windows) do
				if window_has_sheet(window_item) then
					return true
				end
			end
			return false
		end)
		if not ok then
			return false
		end
		return result == true
	end

	local function document()
		local window = focused_window()
		if window == nil then
			return nil
		end
		return doc_to_path(ax_attr(window, "AXDocument"))
	end

	return {
		read = read,
		select = select,
		close_selected = close_selected,
		has_sheet = has_sheet,
		document = document,
	}
end

local function build_key(H, event)
	local chars = nil
	if type(event.getCharacters) == "function" then
		local ok, value = pcall(function()
			return event:getCharacters()
		end)
		if ok then
			chars = value
		end
	elseif type(event.chars) == "string" then
		chars = event.chars
	end
	local keycode = nil
	if type(event.getKeyCode) == "function" then
		local ok, value = pcall(function()
			return event:getKeyCode()
		end)
		if ok then
			keycode = value
		end
	elseif type(event.keycode) == "number" then
		keycode = event.keycode
	end
	local escape_code = nil
	if H.keycodes ~= nil and H.keycodes.map ~= nil then
		escape_code = H.keycodes.map.escape
	end
	local flags = {}
	if type(event.getFlags) == "function" then
		local ok, value = pcall(function()
			return event:getFlags()
		end)
		if ok and type(value) == "table" then
			flags = value
		end
	elseif type(event.flags) == "table" then
		flags = event.flags
	end
	local autorepeat = false
	if
		H.eventtap ~= nil
		and H.eventtap.event ~= nil
		and H.eventtap.event.properties ~= nil
		and type(event.getProperty) == "function"
	then
		local ok, value = pcall(function()
			return event:getProperty(H.eventtap.event.properties.keyboardEventAutorepeat)
		end)
		if ok and (value == 1 or value == true) then
			autorepeat = true
		end
	elseif event.autorepeat ~= nil then
		autorepeat = event.autorepeat and true or false
	end
	return {
		chars = chars,
		escape = keycode ~= nil and escape_code ~= nil and keycode == escape_code,
		cmd = flags.cmd == true or flags.command == true,
		alt = flags.alt == true or flags.option == true,
		ctrl = flags.ctrl == true or flags.control == true,
		shift = flags.shift == true,
		autorepeat = autorepeat,
	}
end

--- Stop the tap, watcher, and pending timers. Keeps `lastBatch` in memory.
function M.stop()
	if runtime.tap ~= nil and type(runtime.tap.stop) == "function" then
		pcall(function()
			runtime.tap:stop()
		end)
	end
	runtime.tap = nil
	if runtime.watcher ~= nil and type(runtime.watcher.stop) == "function" then
		pcall(function()
			runtime.watcher:stop()
		end)
	end
	runtime.watcher = nil
	if type(runtime.timers) == "table" then
		for _, timer in ipairs(runtime.timers) do
			if timer ~= nil and type(timer.stop) == "function" then
				pcall(function()
					timer:stop()
				end)
			end
		end
	end
	runtime.timers = {}
	runtime.running = false
	if runtime.leader ~= nil and type(runtime.leader.cancel) == "function" then
		pcall(function()
			runtime.leader:cancel()
		end)
	end
end

--- Start (or restart) the Highlights leader tap. `options` overrides exist for tests.
function M.start(options)
	options = options or {}
	local H = options.hs or hs
	if H == nil then
		error("highlights_tab_keys requires hs")
	end
	M.stop()

	runtime.leader = HighlightsTabs.new_leader({ timeout = HighlightsTabs.LEADER_TIMEOUT_SECONDS })
	runtime.running = false
	if type(runtime.lastBatch) ~= "table" then
		runtime.lastBatch = {}
	end
	runtime.timers = {}

	local adapter = options.adapter or make_real_adapter(H)
	local after_fn = options.after
	if type(after_fn) ~= "function" then
		after_fn = function(seconds, fn)
			local timer = nil
			timer = H.timer.doAfter(seconds, function()
				if runtime.timers ~= nil then
					for index, pending in ipairs(runtime.timers) do
						if pending == timer then
							table.remove(runtime.timers, index)
							break
						end
					end
				end
				fn()
			end)
			if timer ~= nil then
				table.insert(runtime.timers, timer)
			end
			return timer
		end
	end
	local now_fn = options.now
	if type(now_fn) ~= "function" then
		now_fn = function()
			if H.timer ~= nil and type(H.timer.secondsSinceEpoch) == "function" then
				local ok, value = pcall(function()
					return H.timer.secondsSinceEpoch()
				end)
				if ok and type(value) == "number" then
					return value
				end
			end
			return os.time()
		end
	end
	local alert_fn = options.alert
	if type(alert_fn) ~= "function" then
		alert_fn = function(message)
			H.alert.show(message, 1.5)
		end
	end
	local open_fn = options.open
	if type(open_fn) ~= "function" then
		open_fn = function(paths)
			local args = { "-b", M.BUNDLE_ID }
			for _, path in ipairs(paths) do
				table.insert(args, path)
			end
			local task = H.task.new("/usr/bin/open", nil, args)
			if task ~= nil and type(task.start) == "function" then
				pcall(function()
					task:start()
				end)
			end
		end
	end
	local can_arm = make_can_arm(H)

	local deps = {
		read = adapter.read,
		select = adapter.select,
		close_selected = adapter.close_selected,
		has_sheet = adapter.has_sheet,
		document = adapter.document,
		after = after_fn,
		now = now_fn,
	}

	local function show(message)
		pcall(function()
			alert_fn(message)
		end)
	end

	local function dispatch(command)
		if runtime.running then
			show(HighlightsTabs.BUSY_MESSAGE)
			return
		end
		if command == "reopen" then
			local batch = runtime.lastBatch
			if type(batch) ~= "table" or #batch == 0 then
				show(HighlightsTabs.message("reopen", { status = "empty" }))
				return
			end
			local count = #batch
			local paths = batch
			runtime.lastBatch = {}
			pcall(function()
				open_fn(paths)
			end)
			show(HighlightsTabs.message("reopen", { status = "reopened", count = count, closed = count }))
			return
		end
		runtime.running = true
		local ok, err = pcall(function()
			HighlightsTabs.run_close(command, deps, function(result)
				runtime.running = false
				if
					type(result) == "table"
					and (result.status == "done" or result.status == "needs_attention" or result.status == "failed")
					and tonumber(result.closed or 0) > 0
					and type(result.paths) == "table"
					and #result.paths > 0
				then
					runtime.lastBatch = result.paths
				elseif type(result) == "table" and result.status == "done" and tonumber(result.closed or 0) > 0 then
					-- A run that closed tabs but recorded no paths clears the batch.
					runtime.lastBatch = {}
				end
				show(HighlightsTabs.message(command, result or {}))
			end)
		end)
		if not ok then
			runtime.running = false
			pcall(function()
				H.printf("Bob Highlights tab keys run failed: %s", tostring(err))
			end)
		end
	end

	local function handle_key(event)
		if frontmost_bundle_id(H) ~= M.BUNDLE_ID then
			if runtime.leader ~= nil and type(runtime.leader.cancel) == "function" then
				pcall(function()
					runtime.leader:cancel()
				end)
			end
			return false
		end
		local key = build_key(H, event)
		local outcome = runtime.leader:on_key(key, now_fn(), can_arm)
		if outcome ~= nil and outcome.command ~= nil then
			after_fn(0, function()
				dispatch(outcome.command)
			end)
		end
		if outcome ~= nil and outcome.swallow then
			return true
		end
		return false
	end

	local tap_callback = function(event)
		local ok, swallow = xpcall(function()
			return handle_key(event)
		end, debug.traceback)
		if not ok then
			pcall(function()
				H.printf("Bob Highlights tab keys callback failed: %s", tostring(swallow))
			end)
			return false
		end
		if swallow then
			return true
		end
		return false
	end

	local key_down = nil
	if H.eventtap ~= nil and H.eventtap.event ~= nil and H.eventtap.event.types ~= nil then
		key_down = H.eventtap.event.types.keyDown
	end
	runtime.tap = H.eventtap.new({ key_down }, tap_callback)

	local watcher_callback = function(_, event_type, app_object)
		local ok, err = xpcall(function()
			local bid = nil
			if app_object ~= nil then
				if type(app_object.bundleID) == "function" then
					local ok_bid, value = pcall(function()
						return app_object:bundleID()
					end)
					if ok_bid then
						bid = value
					end
				elseif type(app_object.bundleID) == "string" then
					bid = app_object.bundleID
				end
			end
			local activated = H.application.watcher.activated
			local deactivated = H.application.watcher.deactivated
			local terminated = H.application.watcher.terminated
			if bid == M.BUNDLE_ID and event_type == activated then
				if runtime.tap ~= nil and type(runtime.tap.start) == "function" then
					pcall(function()
						runtime.tap:start()
					end)
					if type(runtime.tap.isEnabled) == "function" then
						local ok_enabled, enabled = pcall(function()
							return runtime.tap:isEnabled()
						end)
						if ok_enabled and not enabled then
							pcall(function()
								runtime.tap:stop()
							end)
							pcall(function()
								runtime.tap:start()
							end)
						end
					end
				end
			elseif bid == M.BUNDLE_ID and (event_type == deactivated or event_type == terminated) then
				if runtime.tap ~= nil and type(runtime.tap.stop) == "function" then
					pcall(function()
						runtime.tap:stop()
					end)
				end
				if runtime.leader ~= nil and type(runtime.leader.cancel) == "function" then
					pcall(function()
						runtime.leader:cancel()
					end)
				end
			end
		end, debug.traceback)
		if not ok then
			pcall(function()
				H.printf("Bob Highlights tab keys watcher failed: %s", tostring(err))
			end)
		end
	end

	runtime.watcher = H.application.watcher.new(watcher_callback)
	if runtime.watcher ~= nil and type(runtime.watcher.start) == "function" then
		pcall(function()
			runtime.watcher:start()
		end)
	end
	if frontmost_bundle_id(H) == M.BUNDLE_ID then
		if runtime.tap ~= nil and type(runtime.tap.start) == "function" then
			pcall(function()
				runtime.tap:start()
			end)
		end
	end

	runtime._deps_for_tests = deps
	runtime._can_arm_for_tests = can_arm
	runtime._dispatch_for_tests = dispatch
	runtime._handle_key_for_tests = handle_key
end

return M
