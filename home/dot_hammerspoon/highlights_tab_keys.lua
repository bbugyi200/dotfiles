-- Hammerspoon Highlights tab-close, page, and scroll keys runtime (hs glue).
-- Pure state machines and runners live in `highlights_tabs.lua` and
-- `highlights_pages.lua`; this module wires one event tap, watchers, and AX.
local HighlightsTabs = require("highlights_tabs")
local HighlightsPages = require("highlights_pages")

local M = {}

M.BUNDLE_ID = HighlightsTabs.BUNDLE_ID
M.PAGE_URL_EVENT = "bob-highlights-page"

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

--- Find the PDF scroll area and its shared document container to depth 3.
--- Never descends into scroll, web, text, table, or outline roles.
function M.find_pdf_view(window, depth)
	depth = depth or 0
	if window == nil or depth > 3 then
		return nil
	end
	local role = ax_attr(window, "AXRole")
	if role == "AXScrollArea" then
		local children = ax_attr(window, "AXChildren")
		if type(children) == "table" then
			for _, child in ipairs(children) do
				if ax_attr(child, "AXSubrole") == "AXSharedDocumentContainer" then
					local pages = ax_attr(child, "AXChildren")
					if type(pages) == "table" and pages[1] ~= nil and ax_attr(pages[1], "AXRole") == "AXPage" then
						return window, child
					end
				end
			end
		end
		return nil
	end
	if role ~= nil and EXCLUDED_ROLES[role] then
		return nil
	end
	local children = ax_attr(window, "AXChildren")
	if type(children) ~= "table" then
		return nil
	end
	for _, child in ipairs(children) do
		local area, document = M.find_pdf_view(child, depth + 1)
		if area ~= nil then
			return area, document
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

local function ax_flag(value)
	if value == true then
		return true
	end
	local value_type = type(value)
	if value_type == "number" or value_type == "string" then
		return tonumber(value) == 1
	end
	return false
end

local function percent_decode(path)
	return (path:gsub("%%(%x%x)", function(hex)
		return string.char(tonumber(hex, 16))
	end))
end

local function doc_to_path(value)
	if type(value) ~= "string" or value == "" then
		return nil
	end
	if value:sub(1, 7) == "file://" then
		local path = value:gsub("^file://[^/]*", "")
		path = path:gsub("^localhost", "")
		path = percent_decode(path)
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

local function coordinate(value, primary, alternate)
	if type(value) ~= "table" then
		return nil
	end
	local result = value[primary]
	if result == nil and alternate ~= nil then
		result = value[alternate]
	end
	return tonumber(result)
end

local function element_frame(element)
	local frame = ax_attr(element, "AXFrame")
	local x = coordinate(frame, "x")
	local y = coordinate(frame, "y")
	local w = coordinate(frame, "w", "width")
	local h = coordinate(frame, "h", "height")
	if x ~= nil and y ~= nil and w ~= nil and h ~= nil then
		return { x = x, y = y, w = w, h = h }
	end
	local position = ax_attr(element, "AXPosition")
	local size = ax_attr(element, "AXSize")
	x = coordinate(position, "x")
	y = coordinate(position, "y")
	w = coordinate(size, "w", "width")
	h = coordinate(size, "h", "height")
	if x == nil or y == nil or w == nil or h == nil then
		return nil
	end
	return { x = x, y = y, w = w, h = h }
end

local function pdf_page_element(document, page_number)
	local children = ax_attr(document, "AXChildren")
	if type(children) ~= "table" then
		return nil
	end
	local fast = children[page_number]
	if fast ~= nil and tonumber(ax_attr(fast, "AXPageIndex")) == page_number - 1 then
		return fast
	end
	for _, child in ipairs(children) do
		if tonumber(ax_attr(child, "AXPageIndex")) == page_number - 1 then
			return child
		end
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
			local selected = ax_flag(raw_value)
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

	local function has_document()
		return document() ~= nil
	end

	local function page_info()
		local window = focused_window()
		if window == nil then
			return nil, "couldn't read Highlights' page number"
		end
		local page, count = HighlightsPages.parse_title(ax_attr(window, "AXTitle"))
		local path = document()
		if page == nil or count == nil or path == nil then
			return nil, "couldn't read Highlights' page number"
		end
		return { page = page, count = count, document = path }
	end

	local function current_pdf_view()
		local window = focused_window()
		if window == nil then
			return nil
		end
		return M.find_pdf_view(window)
	end

	local function has_pdf_view()
		local area, shared_document = current_pdf_view()
		return area ~= nil and shared_document ~= nil
	end

	local function vertical_scrollbar(area)
		local bar = ax_attr(area, "AXVerticalScrollBar")
		if bar ~= nil then
			return bar
		end
		local children = ax_attr(area, "AXChildren")
		if type(children) ~= "table" then
			return nil
		end
		for _, child in ipairs(children) do
			if
				ax_attr(child, "AXRole") == "AXScrollBar"
				and ax_attr(child, "AXOrientation") == "AXVerticalOrientation"
			then
				return child
			end
		end
		return nil
	end

	local function scroll_to(page_number)
		local area, shared_document = current_pdf_view()
		if area == nil or shared_document == nil then
			return false
		end
		local page = pdf_page_element(shared_document, page_number)
		local area_frame = element_frame(area)
		local document_frame = element_frame(shared_document)
		local page_frame = element_frame(page)
		local bar = vertical_scrollbar(area)
		if page == nil or area_frame == nil or document_frame == nil or page_frame == nil or bar == nil then
			return false
		end
		local maximum = document_frame.h - area_frame.h
		local value = 0
		if page_number ~= 1 and maximum > 0 then
			value = math.max(0, math.min(1, (page_frame.y - document_frame.y) / maximum))
		end
		if type(bar.setAttributeValue) ~= "function" then
			return false
		end
		local ok, result = pcall(function()
			return bar:setAttributeValue("AXValue", value)
		end)
		return ok and result ~= nil
	end

	local function scroll_geometry()
		local area, shared_document = current_pdf_view()
		if area == nil or shared_document == nil then
			return nil, "couldn't find the PDF view"
		end
		local area_frame = element_frame(area)
		local document_frame = element_frame(shared_document)
		local bar = vertical_scrollbar(area)
		local value = tonumber(ax_attr(bar, "AXValue"))
		if area_frame == nil or document_frame == nil or bar == nil or value == nil then
			return nil, "couldn't read the scroll position"
		end
		return { value = value, view_h = area_frame.h, document_h = document_frame.h, bar = bar }
	end

	local function set_scroll_value(geometry, value)
		local bar = geometry and geometry.bar
		if bar == nil or type(bar.setAttributeValue) ~= "function" then
			return false, "couldn't set the scroll bar"
		end
		local ok, result = pcall(function()
			return bar:setAttributeValue("AXValue", value)
		end)
		if not ok or result == nil or result == false then
			return false, "couldn't set the scroll bar"
		end
		local new_value = tonumber(ax_attr(bar, "AXValue"))
		if new_value == nil then
			return false, "couldn't read the scroll position"
		end
		if math.abs(new_value - geometry.value) < 1e-6 then
			return false, "the scroll bar didn't move"
		end
		return true
	end

	local function scroll_to_visible(page_number)
		local _, shared_document = current_pdf_view()
		local page = pdf_page_element(shared_document, page_number)
		if page == nil or type(page.performAction) ~= "function" then
			return false
		end
		local ok, result = pcall(function()
			return page:performAction("AXScrollToVisible")
		end)
		return ok and result ~= false and result ~= nil
	end

	local function landed(page_number)
		local area, shared_document = current_pdf_view()
		if area == nil or shared_document == nil then
			return false
		end
		local page_frame = element_frame(pdf_page_element(shared_document, page_number))
		local area_frame = element_frame(area)
		if page_frame == nil or area_frame == nil then
			return false
		end
		local page_bottom = page_frame.y + page_frame.h
		local area_bottom = area_frame.y + area_frame.h
		local midpoint = area_frame.y + area_frame.h / 2
		local covers_midpoint = page_frame.y <= midpoint and page_bottom >= midpoint
		local entirely_visible = page_frame.y >= area_frame.y and page_bottom <= area_bottom
		return covers_midpoint or entirely_visible
	end

	return {
		read = read,
		select = select,
		close_selected = close_selected,
		has_sheet = has_sheet,
		document = document,
		has_document = has_document,
		page_info = page_info,
		has_pdf_view = has_pdf_view,
		scroll_to = scroll_to,
		scroll_geometry = scroll_geometry,
		set_scroll_value = set_scroll_value,
		scroll_to_visible = scroll_to_visible,
		landed = landed,
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
	local plain = nil
	if type(event.getCharacters) == "function" then
		local ok, value = pcall(function()
			return event:getCharacters(true)
		end)
		if ok then
			plain = value
		end
	end
	if type(plain) ~= "string" then
		if type(event.plain) == "string" then
			plain = event.plain
		else
			plain = chars
		end
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
		plain = plain,
		escape = keycode ~= nil and escape_code ~= nil and keycode == escape_code,
		cmd = flags.cmd == true or flags.command == true,
		alt = flags.alt == true or flags.option == true,
		ctrl = flags.ctrl == true or flags.control == true,
		shift = flags.shift == true,
		autorepeat = autorepeat,
	}
end

--- Stop the tap, watcher, and pending timers. Keeps `lastBatch` and jump history in memory.
function M.stop()
	runtime.page_request_generation = (tonumber(runtime.page_request_generation) or 0) + 1
	runtime.pending_page_request = nil
	local url_timer = runtime.url_timer
	runtime.url_timer = nil
	if url_timer ~= nil and type(url_timer.stop) == "function" then
		pcall(function()
			url_timer:stop()
		end)
	end
	if runtime.url_event ~= nil and type(runtime.url_event.bind) == "function" then
		pcall(function()
			runtime.url_event.bind(M.PAGE_URL_EVENT, nil)
		end)
	end
	runtime.url_event = nil
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
			if timer ~= nil and timer ~= url_timer and type(timer.stop) == "function" then
				pcall(function()
					timer:stop()
				end)
			end
		end
	end
	runtime.timers = {}
	runtime.running = false
	runtime.page_running = false
	runtime.scroll_batch = nil
	runtime.scroll_scheduled = false
	if runtime.leader ~= nil and type(runtime.leader.cancel) == "function" then
		pcall(function()
			runtime.leader:cancel()
		end)
	end
	if runtime.page_keys ~= nil and type(runtime.page_keys.cancel) == "function" then
		pcall(function()
			runtime.page_keys:cancel()
		end)
	end
end

--- Start (or restart) the Highlights tab and page key tap. Test overrides are supported.
function M.start(options)
	options = options or {}
	local H = options.hs or hs
	if H == nil then
		error("highlights_tab_keys requires hs")
	end
	M.stop()

	runtime.leader = HighlightsTabs.new_leader({ timeout = HighlightsTabs.LEADER_TIMEOUT_SECONDS })
	runtime.page_keys = HighlightsPages.new_keys({ timeout = HighlightsPages.KEY_TIMEOUT_SECONDS })
	runtime.running = false
	runtime.page_running = false
	if type(runtime.lastBatch) ~= "table" then
		runtime.lastBatch = {}
	end
	if
		type(runtime.history) ~= "table"
		or type(runtime.history.back) ~= "table"
		or type(runtime.history.forward) ~= "table"
	then
		runtime.history = HighlightsPages.new_history()
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
	local can_arm_pages = function()
		if not can_arm() or type(adapter.has_document) ~= "function" then
			return false
		end
		local ok, result = pcall(adapter.has_document)
		return ok and result == true
	end

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

	local function dispatch_page(command)
		if runtime.running then
			show(HighlightsTabs.BUSY_MESSAGE)
			return
		end
		if runtime.page_running then
			show(HighlightsPages.BUSY_MESSAGE)
			return
		end
		runtime.page_running = true
		local page_deps = {
			page_info = adapter.page_info,
			scroll_to = adapter.scroll_to,
			scroll_to_visible = adapter.scroll_to_visible,
			landed = adapter.landed,
			after = after_fn,
			now = now_fn,
			same_document = function(path_a, path_b)
				local fs = H.fs
				local attributes = fs
						and type(fs.attributes) == "function"
						and function(path)
							return fs.attributes(path)
						end
					or nil
				return HighlightsPages.same_file(path_a, path_b, attributes)
			end,
			log = function(message)
				H.printf("%s", message)
			end,
		}
		local ok, err = pcall(function()
			HighlightsPages.run(command, runtime.history, page_deps, function(result)
				runtime.page_running = false
				local message = HighlightsPages.message(result)
				if message ~= nil then
					show(message)
				end
				if type(result) == "table" and result.status == "failed" then
					pcall(function()
						H.printf(
							"Bob Highlights page keys %s failed: %s",
							tostring(result.kind),
							tostring(result.reason)
						)
					end)
				end
			end)
		end)
		if not ok then
			runtime.page_running = false
			local result = { status = "failed", kind = command and command.kind, reason = "couldn't find the PDF view" }
			show(HighlightsPages.message(result))
			pcall(function()
				H.printf("Bob Highlights page keys %s failed: %s", tostring(result.kind), tostring(err))
			end)
		end
	end

	local scroll_deps = {
		scroll_geometry = adapter.scroll_geometry,
		set_scroll_value = adapter.set_scroll_value,
	}

	local function flush_scroll()
		runtime.scroll_scheduled = false
		local batch = runtime.scroll_batch
		runtime.scroll_batch = nil
		if batch == nil or runtime.running or runtime.page_running then
			return
		end
		local ok, result = pcall(HighlightsPages.scroll, batch, scroll_deps)
		if not ok then
			result = { status = "failed", kind = "scroll", reason = tostring(result) }
		end
		if type(result) == "table" and result.status == "failed" then
			pcall(function()
				H.printf("Bob Highlights scroll keys failed: %s", tostring(result.reason))
			end)
			if batch.fresh == true then
				show(HighlightsPages.message(result))
			end
		end
	end

	local function queue_scroll(command)
		if runtime.running or runtime.page_running then
			return
		end
		runtime.scroll_batch = HighlightsPages.add_scroll(runtime.scroll_batch, command)
		if not runtime.scroll_scheduled then
			runtime.scroll_scheduled = true
			after_fn(0, flush_scroll)
		end
	end

	local function safe_read(fn)
		if type(fn) ~= "function" then
			return nil
		end
		local ok, value = pcall(fn)
		if ok then
			return value
		end
		return nil
	end

	local function stop_url_timer()
		local timer = runtime.url_timer
		runtime.url_timer = nil
		if timer ~= nil and type(timer.stop) == "function" then
			pcall(function()
				timer:stop()
			end)
		end
		if type(runtime.timers) == "table" then
			for index, pending in ipairs(runtime.timers) do
				if pending == timer then
					table.remove(runtime.timers, index)
					break
				end
			end
		end
	end

	local function schedule_page_request_poll(generation, poll)
		local timer = nil
		timer = after_fn(HighlightsPages.PAGE_REQUEST_POLL_SECONDS, function()
			if generation ~= runtime.page_request_generation then
				return
			end
			if runtime.url_timer == timer then
				runtime.url_timer = nil
			end
			poll()
		end)
		runtime.url_timer = timer
	end

	local function handle_page_url(params)
		runtime.page_request_generation = (tonumber(runtime.page_request_generation) or 0) + 1
		stop_url_timer()
		runtime.pending_page_request = nil
		local request, reason = HighlightsPages.parse_page_request(params)
		if request == nil then
			pcall(function()
				H.printf("Bob Highlights page request rejected: %s", tostring(reason))
			end)
			return
		end

		local generation = runtime.page_request_generation
		local wait_state = { saw_front = false, stable_page = nil }
		local deadline = now_fn() + HighlightsPages.PAGE_REQUEST_TIMEOUT_SECONDS
		runtime.pending_page_request = request

		local function poll()
			if generation ~= runtime.page_request_generation then
				return
			end
			local frontmost = frontmost_bundle_id(H) == M.BUNDLE_ID
			local observation = {
				frontmost = frontmost,
				busy = runtime.running == true or runtime.page_running == true,
				same_document = false,
				has_pdf_view = false,
				title_valid = false,
			}
			if frontmost then
				local current_path = safe_read(adapter.document)
				local fs = H.fs
				local attributes = fs
						and type(fs.attributes) == "function"
						and function(path)
							return fs.attributes(path)
						end
					or nil
				observation.same_document = HighlightsPages.same_file(request.path, current_path, attributes)
				local info = safe_read(adapter.page_info)
				if type(info) == "table" then
					observation.page = info.page
					observation.title_valid = type(info.page) == "number"
						and type(info.count) == "number"
						and info.page >= 1
						and info.page <= info.count
						and info.page % 1 == 0
				end
				observation.has_pdf_view = safe_read(adapter.has_pdf_view) == true
			end
			local status = HighlightsPages.page_request_step(wait_state, observation)
			if status == "cancel" then
				runtime.pending_page_request = nil
				stop_url_timer()
				return
			elseif status == "ready" then
				runtime.pending_page_request = nil
				stop_url_timer()
				dispatch_page({
					kind = "goto",
					target = request.page,
					origin = "url",
					document = request.path,
				})
				return
			end
			if now_fn() >= deadline then
				runtime.pending_page_request = nil
				stop_url_timer()
				show(HighlightsPages.message({
					status = "failed",
					kind = "goto",
					page = request.page,
					reason = "the PDF didn't come to the front",
				}))
				return
			end
			schedule_page_request_poll(generation, poll)
		end

		poll()
	end

	-- hs.urlevent callbacks receive (eventName, params, senderPID): params is the
	-- second argument, already percent-decoded by Hammerspoon.
	local function on_page_url(_event_name, params)
		handle_page_url(params)
	end

	local url_event = options.urlevent or H.urlevent
	if url_event ~= nil and type(url_event.bind) == "function" then
		runtime.url_event = url_event
		local ok, err = pcall(function()
			url_event.bind(M.PAGE_URL_EVENT, on_page_url)
		end)
		if not ok then
			runtime.url_event = nil
			pcall(function()
				H.printf("Bob Highlights page URL binding failed: %s", tostring(err))
			end)
		end
	end

	local function dispatch(command)
		if runtime.page_running then
			show(HighlightsPages.BUSY_MESSAGE)
			return
		end
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
				if type(result) == "table" and result.status == "failed" then
					pcall(function()
						H.printf("Bob Highlights tab keys %s failed: %s", command, tostring(result.reason))
					end)
				end
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
			if runtime.page_keys ~= nil and type(runtime.page_keys.cancel) == "function" then
				pcall(function()
					runtime.page_keys:cancel()
				end)
			end
			return false
		end
		local key = build_key(H, event)
		local now = now_fn()
		local leader_was_offered = runtime.leader:is_pending()
		if leader_was_offered then
			local leader_outcome = runtime.leader:on_key(key, now, can_arm)
			if leader_outcome ~= nil and (leader_outcome.swallow or leader_outcome.command ~= nil) then
				if leader_outcome.command ~= nil then
					after_fn(0, function()
						dispatch(leader_outcome.command)
					end)
				end
				return leader_outcome.swallow == true
			end
		end

		local page_outcome = runtime.page_keys:on_key(key, now, can_arm_pages)
		if page_outcome ~= nil and (page_outcome.swallow or page_outcome.command ~= nil) then
			if page_outcome.command ~= nil then
				if page_outcome.command.kind == "scroll" then
					queue_scroll(page_outcome.command)
				else
					after_fn(0, function()
						dispatch_page(page_outcome.command)
					end)
				end
			end
			return page_outcome.swallow == true
		end

		if not leader_was_offered then
			local leader_outcome = runtime.leader:on_key(key, now, can_arm)
			if leader_outcome ~= nil and leader_outcome.command ~= nil then
				after_fn(0, function()
					dispatch(leader_outcome.command)
				end)
			end
			return leader_outcome ~= nil and leader_outcome.swallow == true
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
				if runtime.page_keys ~= nil and type(runtime.page_keys.cancel) == "function" then
					pcall(function()
						runtime.page_keys:cancel()
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
	runtime._page_deps_for_tests = {
		page_info = adapter.page_info,
		scroll_to = adapter.scroll_to,
		scroll_to_visible = adapter.scroll_to_visible,
		landed = adapter.landed,
		after = after_fn,
		now = now_fn,
	}
	runtime._scroll_deps_for_tests = scroll_deps
	runtime._can_arm_for_tests = can_arm
	runtime._can_arm_pages_for_tests = can_arm_pages
	runtime._dispatch_for_tests = dispatch
	runtime._page_dispatch_for_tests = dispatch_page
	runtime._page_url_handler_for_tests = handle_page_url
	runtime._handle_key_for_tests = handle_key
end

return M
