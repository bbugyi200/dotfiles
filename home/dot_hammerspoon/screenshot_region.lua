local M = {}

local SETTINGS_KEY = "macscrotLastRegion"
local MIN_SIZE = 16
local HANDLE_SIZE = 10
local HANDLE_HIT_RADIUS = 6
local DRAG_THRESHOLD = 3
local CAPTURE_DELAY = 0.08
local HINT_WIDTH = 420
local HINT_HEIGHT = 42
local HINT_TEXT =
	"Drag: new box · ⌘-drag: move · Corners: resize · F: full screen · W: window\nEnter: capture · ⌘Enter: capture + save default · Esc: cancel"

local activeSession = nil
local unpackTable = table.unpack or unpack

local function round(value)
	return math.floor((tonumber(value) or 0) + 0.5)
end

local function clamp(value, low, high)
	if high < low then
		return low
	end
	if value < low then
		return low
	end
	if value > high then
		return high
	end
	return value
end

local function copyRect(rect)
	return {
		x = tonumber(rect.x) or 0,
		y = tonumber(rect.y) or 0,
		w = tonumber(rect.w) or 0,
		h = tonumber(rect.h) or 0,
	}
end

local function normalizedRect(x1, y1, x2, y2)
	local x = math.min(x1, x2)
	local y = math.min(y1, y2)
	local w = math.abs(x2 - x1)
	local h = math.abs(y2 - y1)
	return { x = x, y = y, w = w, h = h }
end

local function roundedRect(rect)
	return {
		x = round(rect.x),
		y = round(rect.y),
		w = math.max(MIN_SIZE, round(rect.w)),
		h = math.max(MIN_SIZE, round(rect.h)),
	}
end

local function frameContainsPoint(frame, point)
	return point.x >= frame.x and point.x <= frame.x + frame.w and point.y >= frame.y and point.y <= frame.y + frame.h
end

local function frameContainsRect(frame, rect)
	return rect.x >= frame.x
		and rect.y >= frame.y
		and rect.x + rect.w <= frame.x + frame.w
		and rect.y + rect.h <= frame.y + frame.h
end

local function screenForRect(rect)
	for _, screen in ipairs(hs.screen.allScreens()) do
		if frameContainsRect(screen:frame(), rect) then
			return screen
		end
	end
	return nil
end

local function activeScreen()
	return hs.mouse.getCurrentScreen() or hs.screen.mainScreen()
end

local function defaultRegion(frame)
	local width = math.max(MIN_SIZE, math.floor(frame.w * 0.6))
	local height = math.max(MIN_SIZE, math.floor(frame.h * 0.6))
	return {
		x = math.floor(frame.x + (frame.w - width) / 2),
		y = math.floor(frame.y + (frame.h - height) / 2),
		w = width,
		h = height,
	}
end

local function clampRegionToFrame(rect, frame)
	local width = clamp(rect.w, MIN_SIZE, frame.w)
	local height = clamp(rect.h, MIN_SIZE, frame.h)
	local x = clamp(rect.x, frame.x, frame.x + frame.w - width)
	local y = clamp(rect.y, frame.y, frame.y + frame.h - height)
	return { x = x, y = y, w = width, h = height }
end

local function keyIs(event, name)
	if type(event.getCharacters) == "function" then
		local ok, chars = pcall(function()
			return event:getCharacters()
		end)
		if ok and type(chars) == "string" and chars:lower() == name then
			return true
		end
	end
	return type(event.getKeyCode) == "function"
		and hs.keycodes
		and hs.keycodes.map
		and event:getKeyCode() == hs.keycodes.map[name]
end

local function frontmostWindowAt(point, frame)
	if not hs.window or type(hs.window.orderedWindows) ~= "function" then
		return nil
	end
	local ok, windows = pcall(hs.window.orderedWindows)
	if not ok or type(windows) ~= "table" then
		return nil
	end
	for _, window in ipairs(windows) do
		local standard, hammerspoon, windowFrame = false, false, nil
		pcall(function()
			standard = window:isStandard() == true
		end)
		pcall(function()
			local app = window:application()
			hammerspoon = app and app:bundleID() == "org.hammerspoon.Hammerspoon"
		end)
		pcall(function()
			windowFrame = window:frame()
		end)
		if standard and not hammerspoon and windowFrame and frameContainsPoint(windowFrame, point) then
			return clampRegionToFrame(windowFrame, frame)
		end
	end
	return nil
end

local function regionFromSettings(key)
	if type(key) ~= "string" or key == "" then
		return nil
	end
	local saved = hs.settings.get(key)
	if type(saved) ~= "table" then
		return nil
	end
	local rect = copyRect(saved)
	if rect.w < MIN_SIZE or rect.h < MIN_SIZE then
		return nil
	end
	local savedScreen = screenForRect(rect)
	if not savedScreen then
		return nil
	end
	return savedScreen, clampRegionToFrame(rect, savedScreen:frame())
end

local function loadInitialRegion(settingsKey, fallbackSettingsKey)
	local savedScreen, savedRegion = regionFromSettings(settingsKey)
	if savedScreen then
		return savedScreen, savedRegion
	end
	savedScreen, savedRegion = regionFromSettings(fallbackSettingsKey)
	if savedScreen then
		return savedScreen, savedRegion
	end
	local screen = activeScreen()
	return screen, defaultRegion(screen:frame())
end

local function toLocal(rect, frame)
	return {
		x = rect.x - frame.x,
		y = rect.y - frame.y,
		w = rect.w,
		h = rect.h,
	}
end

local function localFrame(rect, frame)
	return {
		x = clamp(rect.x, 0, frame.w),
		y = clamp(rect.y, 0, frame.h),
		w = math.max(0, rect.w),
		h = math.max(0, rect.h),
	}
end

local function floatingFrame(screenFrame, preferredX, preferredY, width, height)
	width = math.min(width, math.max(1, screenFrame.w - 16))
	height = math.min(height, math.max(1, screenFrame.h - 16))
	return {
		x = clamp(preferredX, 8, screenFrame.w - width - 8),
		y = clamp(preferredY, 8, screenFrame.h - height - 8),
		w = width,
		h = height,
	}
end

local dimColor = { white = 0, alpha = 0.56 }
local labelColor = { white = 0, alpha = 0.72 }
local textColor = { white = 1, alpha = 0.98 }
local blue = { red = 0.04, green = 0.52, blue = 1, alpha = 1 }
local handleFill = { white = 1, alpha = 0.96 }
local BADGE_DOT_RADIUS = 4

local function resolveText(value, state, fallback)
	if type(value) == "function" then
		local ok, result = pcall(value, state)
		if ok and type(result) == "string" then
			return result
		end
		return fallback
	end
	if type(value) == "string" then
		return value
	end
	return fallback
end

local function sizeLabelText(region, badge)
	local width = round(region.w)
	local height = round(region.h)
	if type(badge) == "string" and badge ~= "" then
		return string.format("%s · %d × %d", badge, width, height)
	end
	return string.format("%d x %d", width, height)
end

local function measureText(canvas, spec)
	if canvas == nil or type(canvas.minimumTextSize) ~= "function" then
		return nil
	end
	local ok, size = pcall(function()
		return canvas:minimumTextSize(spec)
	end)
	if not ok or type(size) ~= "table" then
		return nil
	end
	local width = tonumber(size.w) or tonumber(size.width)
	local height = tonumber(size.h) or tonumber(size.height)
	if not width or not height then
		return nil
	end
	return width, height
end

local function longestLineLen(text)
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
	return longest, lines
end

local function fittedPillSize(canvas, text, fontSize, defaultW, defaultH, shouldFit, extraW)
	if not shouldFit then
		return defaultW, defaultH
	end
	extraW = extraW or 0
	local spec = {
		text = text,
		textSize = fontSize,
		textFont = ".AppleSystemUIFont",
	}
	local width, height = measureText(canvas, spec)
	if width then
		return math.max(defaultW, math.ceil(width) + 16 + extraW), math.max(defaultH, math.ceil(height) + 10)
	end
	local longest, lines = longestLineLen(text)
	return math.max(defaultW, longest * 7 + 16 + extraW), math.max(defaultH, lines * 16 + 10)
end

local function rectangle(frame, color)
	return {
		type = "rectangle",
		action = "fill",
		frame = frame,
		fillColor = color,
	}
end

local function buildElements(region, screenFrame, style)
	style = style or {}
	local accent = style.accent or blue
	local hintText = style.hint or HINT_TEXT
	local labelText = sizeLabelText(region, style.badge)
	local showBadgeDot = style.accent ~= nil
	local extraBadge = 0
	if showBadgeDot then
		extraBadge = (BADGE_DOT_RADIUS * 2) + 8
	end
	local labelWidth, labelHeight = fittedPillSize(style.canvas, labelText, 13, 116, 24, style.fitBadge, extraBadge)
	local hintWidth, hintHeight = fittedPillSize(style.canvas, hintText, 12, HINT_WIDTH, HINT_HEIGHT, style.fitHint, 0)
	hintWidth = math.min(hintWidth, math.max(1, screenFrame.w - 16))

	local rect = toLocal(region, screenFrame)
	local right = rect.x + rect.w
	local bottom = rect.y + rect.h
	local labelFrame = floatingFrame(screenFrame, rect.x, rect.y - 32, labelWidth, labelHeight)
	if rect.y < 40 then
		labelFrame = floatingFrame(screenFrame, rect.x, bottom + 8, labelWidth, labelHeight)
	end

	local hintFrame = floatingFrame(screenFrame, rect.x, bottom + 38, hintWidth, hintHeight)
	if hintFrame.y + hintFrame.h > screenFrame.h - 8 then
		hintFrame = floatingFrame(screenFrame, rect.x, rect.y - (hintHeight + 38), hintWidth, hintHeight)
	end

	local handleOffset = HANDLE_SIZE / 2
	local function handleFrame(x, y)
		return {
			x = x - handleOffset,
			y = y - handleOffset,
			w = HANDLE_SIZE,
			h = HANDLE_SIZE,
		}
	end

	local elements = {
		rectangle(localFrame({ x = 0, y = 0, w = screenFrame.w, h = rect.y }, screenFrame), dimColor),
		rectangle(localFrame({ x = 0, y = rect.y, w = rect.x, h = rect.h }, screenFrame), dimColor),
		rectangle(localFrame({ x = right, y = rect.y, w = screenFrame.w - right, h = rect.h }, screenFrame), dimColor),
		rectangle(
			localFrame({ x = 0, y = bottom, w = screenFrame.w, h = screenFrame.h - bottom }, screenFrame),
			dimColor
		),
		{
			type = "rectangle",
			action = "stroke",
			frame = rect,
			strokeColor = accent,
			strokeWidth = 2,
		},
		{
			type = "rectangle",
			action = "stroke",
			frame = { x = rect.x + 1, y = rect.y + 1, w = rect.w - 2, h = rect.h - 2 },
			strokeColor = { white = 1, alpha = 0.42 },
			strokeWidth = 1,
		},
		{
			type = "rectangle",
			action = "strokeAndFill",
			id = "nw",
			frame = handleFrame(rect.x, rect.y),
			fillColor = handleFill,
			strokeColor = accent,
			strokeWidth = 1,
		},
		{
			type = "rectangle",
			action = "strokeAndFill",
			id = "ne",
			frame = handleFrame(right, rect.y),
			fillColor = handleFill,
			strokeColor = accent,
			strokeWidth = 1,
		},
		{
			type = "rectangle",
			action = "strokeAndFill",
			id = "sw",
			frame = handleFrame(rect.x, bottom),
			fillColor = handleFill,
			strokeColor = accent,
			strokeWidth = 1,
		},
		{
			type = "rectangle",
			action = "strokeAndFill",
			id = "se",
			frame = handleFrame(right, bottom),
			fillColor = handleFill,
			strokeColor = accent,
			strokeWidth = 1,
		},
		rectangle(labelFrame, labelColor),
	}

	if showBadgeDot then
		table.insert(elements, {
			type = "circle",
			action = "fill",
			id = "badgeDot",
			center = {
				x = labelFrame.x + 8 + BADGE_DOT_RADIUS,
				y = labelFrame.y + (labelFrame.h / 2),
			},
			radius = BADGE_DOT_RADIUS,
			fillColor = accent,
		})
	end

	local labelTextX = labelFrame.x
	local labelTextW = labelFrame.w
	if showBadgeDot then
		local inset = 8 + (BADGE_DOT_RADIUS * 2) + 6
		labelTextX = labelFrame.x + inset
		labelTextW = math.max(0, labelFrame.w - inset - 8)
	end

	table.insert(elements, {
		type = "text",
		action = "fill",
		frame = { x = labelTextX, y = labelFrame.y + 3, w = labelTextW, h = labelFrame.h },
		text = labelText,
		textColor = textColor,
		textFont = ".AppleSystemUIFont",
		textSize = 13,
		textAlignment = "center",
		textLineBreak = "clip",
	})
	table.insert(elements, rectangle(hintFrame, labelColor))
	table.insert(elements, {
		type = "text",
		action = "fill",
		frame = { x = hintFrame.x + 8, y = hintFrame.y + 5, w = hintFrame.w - 16, h = hintFrame.h - 5 },
		text = hintText,
		textColor = textColor,
		textFont = ".AppleSystemUIFont",
		textSize = 12,
		textAlignment = "center",
		textLineBreak = "clip",
	})
	return elements
end

local function pointInRect(point, rect)
	return point.x >= rect.x and point.x <= rect.x + rect.w and point.y >= rect.y and point.y <= rect.y + rect.h
end

local function handleAt(point, rect)
	local half = HANDLE_HIT_RADIUS
	local handles = {
		nw = { x = rect.x - half, y = rect.y - half, w = half * 2, h = half * 2 },
		ne = { x = rect.x + rect.w - half, y = rect.y - half, w = half * 2, h = half * 2 },
		sw = { x = rect.x - half, y = rect.y + rect.h - half, w = half * 2, h = half * 2 },
		se = { x = rect.x + rect.w - half, y = rect.y + rect.h - half, w = half * 2, h = half * 2 },
	}
	for _, name in ipairs({ "nw", "ne", "sw", "se" }) do
		if pointInRect(point, handles[name]) then
			return name
		end
	end
	return nil
end

local function resizeFromHandle(rect, handle, point, frame)
	local left = rect.x
	local top = rect.y
	local right = rect.x + rect.w
	local bottom = rect.y + rect.h
	point = {
		x = clamp(point.x, frame.x, frame.x + frame.w),
		y = clamp(point.y, frame.y, frame.y + frame.h),
	}

	if handle == "nw" then
		left = clamp(point.x, frame.x, right - MIN_SIZE)
		top = clamp(point.y, frame.y, bottom - MIN_SIZE)
	elseif handle == "ne" then
		right = clamp(point.x, left + MIN_SIZE, frame.x + frame.w)
		top = clamp(point.y, frame.y, bottom - MIN_SIZE)
	elseif handle == "sw" then
		left = clamp(point.x, frame.x, right - MIN_SIZE)
		bottom = clamp(point.y, top + MIN_SIZE, frame.y + frame.h)
	elseif handle == "se" then
		right = clamp(point.x, left + MIN_SIZE, frame.x + frame.w)
		bottom = clamp(point.y, top + MIN_SIZE, frame.y + frame.h)
	end

	return { x = left, y = top, w = right - left, h = bottom - top }
end

function M.pick(onConfirm, opts)
	opts = opts or {}
	if activeSession then
		activeSession.cancel("superseded")
	end

	local settingsKey = opts.settingsKey or SETTINGS_KEY
	local fallbackSettingsKey = opts.fallbackSettingsKey
	local captureDelay = CAPTURE_DELAY
	if opts.captureDelay ~= nil then
		captureDelay = opts.captureDelay
	end
	local failureTitle = opts.failureTitle or "Screenshot failed"
	local onCancel = opts.onCancel
	local onKey = opts.onKey
	local callerState
	if type(opts.state) == "table" then
		callerState = opts.state
	else
		callerState = {}
	end

	local screen, region = loadInitialRegion(settingsKey, fallbackSettingsKey)
	local screenFrame = screen:frame()
	local canvas = hs.canvas.new(screenFrame)
	if not canvas then
		hs.notify.show(failureTitle, "", "Could not create screenshot selector")
		return {
			cancel = function() end,
		}
	end

	local drag = nil
	local finished = false
	local tap = nil
	local ctx = nil
	local feedbackTimer = nil

	local function redraw()
		local badge = resolveText(opts.badge, callerState, nil)
		local hint = callerState.windowHint or resolveText(opts.hint, callerState, HINT_TEXT)
		local elements = buildElements(region, screenFrame, {
			accent = opts.accent,
			badge = badge,
			hint = hint,
			canvas = canvas,
			fitBadge = opts.badge ~= nil or opts.accent ~= nil,
			fitHint = true,
		})
		canvas:replaceElements(unpackTable(elements))
	end

	local function cleanup()
		if feedbackTimer then
			feedbackTimer:stop()
			feedbackTimer = nil
		end
		if tap then
			tap:stop()
			tap = nil
		end
		if canvas then
			canvas:hide(0)
			canvas:delete()
			canvas = nil
		end
		activeSession = nil
	end

	local function finish(confirm, saveDefault, cancelReason)
		if finished then
			return
		end
		finished = true

		local finalRegion = roundedRect(clampRegionToFrame(region, screenFrame))
		cleanup()

		if confirm then
			if saveDefault then
				hs.settings.set(settingsKey, finalRegion)
			end
			hs.timer.doAfter(captureDelay, function()
				if onConfirm then
					onConfirm(finalRegion)
				end
			end)
			return
		end

		if type(onCancel) == "function" then
			onCancel(cancelReason)
		end
	end

	ctx = {
		state = callerState,
		region = function()
			return copyRect(region)
		end,
		redraw = redraw,
		cancel = function()
			finish(false, nil, "key")
		end,
		confirm = function(saveDefault)
			if drag then
				return
			end
			finish(region.w >= MIN_SIZE and region.h >= MIN_SIZE, saveDefault == true)
		end,
	}

	local function showNoWindowHint()
		callerState.windowHint = "W: no window here"
		redraw()
		if feedbackTimer then
			feedbackTimer:stop()
		end
		feedbackTimer = hs.timer.doAfter(1.5, function()
			feedbackTimer = nil
			callerState.windowHint = nil
			if not finished then
				redraw()
			end
		end)
	end

	local function eventPoint(event)
		return event:location()
	end

	local function updateNewRegion(anchor, point)
		point = {
			x = clamp(point.x, screenFrame.x, screenFrame.x + screenFrame.w),
			y = clamp(point.y, screenFrame.y, screenFrame.y + screenFrame.h),
		}
		local nextRegion = normalizedRect(anchor.x, anchor.y, point.x, point.y)
		if nextRegion.w < MIN_SIZE then
			nextRegion.w = MIN_SIZE
			if point.x < anchor.x then
				nextRegion.x = anchor.x - MIN_SIZE
			end
		end
		if nextRegion.h < MIN_SIZE then
			nextRegion.h = MIN_SIZE
			if point.y < anchor.y then
				nextRegion.y = anchor.y - MIN_SIZE
			end
		end
		region = clampRegionToFrame(nextRegion, screenFrame)
	end

	local function applyDrag(point)
		if drag.mode == "move" then
			local dx = point.x - drag.startPoint.x
			local dy = point.y - drag.startPoint.y
			region = clampRegionToFrame({
				x = drag.startRegion.x + dx,
				y = drag.startRegion.y + dy,
				w = drag.startRegion.w,
				h = drag.startRegion.h,
			}, screenFrame)
		elseif drag.mode == "resize" then
			region = resizeFromHandle(drag.startRegion, drag.handle, point, screenFrame)
		elseif drag.mode == "new" then
			local dx = math.abs(point.x - drag.anchor.x)
			local dy = math.abs(point.y - drag.anchor.y)
			if dx >= DRAG_THRESHOLD or dy >= DRAG_THRESHOLD then
				drag.moved = true
			end
			if drag.moved then
				updateNewRegion(drag.anchor, point)
			end
		end
	end

	local eventTypes = hs.eventtap.event.types
	tap = hs.eventtap
		.new({
			eventTypes.leftMouseDown,
			eventTypes.leftMouseDragged,
			eventTypes.leftMouseUp,
			eventTypes.keyDown,
		}, function(event)
			local eventType = event:getType()

			if eventType == eventTypes.keyDown then
				local flags = event:getFlags() or {}
				local plainKey = not flags.cmd and not flags.ctrl and not flags.alt and not flags.shift and not flags.fn
				if plainKey and keyIs(event, "f") then
					region = copyRect(screenFrame)
					redraw()
					return true
				elseif plainKey and keyIs(event, "w") then
					local point = hs.mouse.absolutePosition()
					local snapped = frontmostWindowAt(point, screenFrame)
					if snapped then
						region = snapped
						callerState.windowHint = nil
						redraw()
					else
						showNoWindowHint()
					end
					return true
				end
				if type(onKey) == "function" then
					local consumed = onKey(event, ctx)
					if consumed == true or finished then
						return true
					end
				end
				local code = event:getKeyCode()
				if code == hs.keycodes.map.escape then
					finish(false, nil, "esc")
					return true
				end
				if code == hs.keycodes.map["return"] or code == hs.keycodes.map.padenter then
					if drag then
						return true
					end
					local flags = event:getFlags() or {}
					finish(region.w >= MIN_SIZE and region.h >= MIN_SIZE, flags.cmd == true)
					return true
				end
				return true
			end

			local point = eventPoint(event)
			if eventType == eventTypes.leftMouseDown then
				if not frameContainsPoint(screenFrame, point) then
					finish(false, nil, "offscreen")
					return true
				end

				-- Precedence: off-screen closes; ⌘ moves from anywhere; handle resizes; otherwise draw.
				local flags = event:getFlags() or {}
				local handle = handleAt(point, region)
				if flags.cmd then
					drag = {
						mode = "move",
						startPoint = point,
						startRegion = copyRect(region),
					}
				elseif handle then
					drag = {
						mode = "resize",
						handle = handle,
						startRegion = copyRect(region),
					}
				else
					drag = {
						mode = "new",
						anchor = point,
						moved = false,
						startRegion = copyRect(region),
					}
				end
				return true
			end

			if eventType == eventTypes.leftMouseDragged and drag then
				applyDrag(point)
				redraw()
				return true
			end

			if eventType == eventTypes.leftMouseUp then
				if not drag then
					return true
				end
				applyDrag(point)
				if drag.mode == "new" then
					local clampedX = clamp(point.x, screenFrame.x, screenFrame.x + screenFrame.w)
					local clampedY = clamp(point.y, screenFrame.y, screenFrame.y + screenFrame.h)
					local extentX = math.abs(clampedX - drag.anchor.x)
					local extentY = math.abs(clampedY - drag.anchor.y)
					if not drag.moved or (extentX < MIN_SIZE and extentY < MIN_SIZE) then
						region = copyRect(drag.startRegion)
					end
				end
				redraw()
				drag = nil
				return true
			end

			return true
		end)
		:start()

	canvas:level("screenSaver")
	canvas:behaviorAsLabels({ "canJoinAllSpaces", "fullScreenAuxiliary" })
	canvas:clickActivating(false)
	redraw()
	canvas:show()
	canvas:bringToFront(true)

	activeSession = {
		cancel = function(reason)
			finish(false, nil, reason or "superseded")
		end,
	}

	return {
		cancel = function()
			finish(false, nil, "key")
		end,
	}
end

return M
