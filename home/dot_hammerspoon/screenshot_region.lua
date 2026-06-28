local M = {}

local SETTINGS_KEY = "macscrotLastRegion"
local MIN_SIZE = 16
local HANDLE_SIZE = 10
local CAPTURE_DELAY = 0.08

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
	return point.x >= frame.x
		and point.x <= frame.x + frame.w
		and point.y >= frame.y
		and point.y <= frame.y + frame.h
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

local function loadInitialRegion()
	local screen = activeScreen()
	local frame = screen:frame()
	local saved = hs.settings.get(SETTINGS_KEY)

	if type(saved) == "table" then
		local rect = copyRect(saved)
		if rect.w >= MIN_SIZE and rect.h >= MIN_SIZE then
			local savedScreen = screenForRect(rect)
			if savedScreen then
				screen = savedScreen
				frame = screen:frame()
				return screen, clampRegionToFrame(rect, frame)
			end
		end
	end

	return screen, defaultRegion(frame)
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

local function rectangle(frame, color)
	return {
		type = "rectangle",
		action = "fill",
		frame = frame,
		fillColor = color,
	}
end

local function buildElements(region, screenFrame)
	local rect = toLocal(region, screenFrame)
	local right = rect.x + rect.w
	local bottom = rect.y + rect.h
	local labelText = string.format("%d x %d", round(region.w), round(region.h))
	local labelFrame = floatingFrame(screenFrame, rect.x, rect.y - 32, 116, 24)
	if rect.y < 40 then
		labelFrame = floatingFrame(screenFrame, rect.x, bottom + 8, 116, 24)
	end

	local hintWidth = math.min(348, math.max(1, screenFrame.w - 16))
	local hintFrame = floatingFrame(screenFrame, rect.x, bottom + 38, hintWidth, 24)
	if hintFrame.y + hintFrame.h > screenFrame.h - 8 then
		hintFrame = floatingFrame(screenFrame, rect.x, rect.y - 62, hintWidth, 24)
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

	return {
		rectangle(localFrame({ x = 0, y = 0, w = screenFrame.w, h = rect.y }, screenFrame), dimColor),
		rectangle(localFrame({ x = 0, y = rect.y, w = rect.x, h = rect.h }, screenFrame), dimColor),
		rectangle(localFrame({ x = right, y = rect.y, w = screenFrame.w - right, h = rect.h }, screenFrame), dimColor),
		rectangle(localFrame({ x = 0, y = bottom, w = screenFrame.w, h = screenFrame.h - bottom }, screenFrame), dimColor),
		{
			type = "rectangle",
			action = "stroke",
			frame = rect,
			strokeColor = blue,
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
			strokeColor = blue,
			strokeWidth = 1,
		},
		{
			type = "rectangle",
			action = "strokeAndFill",
			id = "ne",
			frame = handleFrame(right, rect.y),
			fillColor = handleFill,
			strokeColor = blue,
			strokeWidth = 1,
		},
		{
			type = "rectangle",
			action = "strokeAndFill",
			id = "sw",
			frame = handleFrame(rect.x, bottom),
			fillColor = handleFill,
			strokeColor = blue,
			strokeWidth = 1,
		},
		{
			type = "rectangle",
			action = "strokeAndFill",
			id = "se",
			frame = handleFrame(right, bottom),
			fillColor = handleFill,
			strokeColor = blue,
			strokeWidth = 1,
		},
		rectangle(labelFrame, labelColor),
		{
			type = "text",
			action = "fill",
			frame = { x = labelFrame.x, y = labelFrame.y + 3, w = labelFrame.w, h = labelFrame.h },
			text = labelText,
			textColor = textColor,
			textFont = ".AppleSystemUIFont",
			textSize = 13,
			textAlignment = "center",
			textLineBreak = "clip",
		},
		rectangle(hintFrame, labelColor),
		{
			type = "text",
			action = "fill",
			frame = { x = hintFrame.x + 8, y = hintFrame.y + 4, w = hintFrame.w - 16, h = hintFrame.h },
			text = "Drag to adjust | Enter to capture | Esc to cancel",
			textColor = textColor,
			textFont = ".AppleSystemUIFont",
			textSize = 12,
			textAlignment = "center",
			textLineBreak = "clip",
		},
	}
end

local function pointInRect(point, rect)
	return point.x >= rect.x
		and point.x <= rect.x + rect.w
		and point.y >= rect.y
		and point.y <= rect.y + rect.h
end

local function handleAt(point, rect)
	local half = HANDLE_SIZE
	local handles = {
		nw = { x = rect.x - half, y = rect.y - half, w = half * 2, h = half * 2 },
		ne = { x = rect.x + rect.w - half, y = rect.y - half, w = half * 2, h = half * 2 },
		sw = { x = rect.x - half, y = rect.y + rect.h - half, w = half * 2, h = half * 2 },
		se = { x = rect.x + rect.w - half, y = rect.y + rect.h - half, w = half * 2, h = half * 2 },
	}
	for name, handle in pairs(handles) do
		if pointInRect(point, handle) then
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

function M.pick(onConfirm)
	if activeSession then
		activeSession.cancel()
	end

	local screen, region = loadInitialRegion()
	local screenFrame = screen:frame()
	local canvas = hs.canvas.new(screenFrame)
	if not canvas then
		hs.notify.show("Screenshot failed", "", "Could not create screenshot selector")
		return
	end

	local drag = nil
	local finished = false
	local tap = nil

	local function redraw()
		local elements = buildElements(region, screenFrame)
		canvas:replaceElements(unpackTable(elements))
	end

	local function cleanup()
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

	local function finish(confirm)
		if finished then
			return
		end
		finished = true

		local finalRegion = roundedRect(clampRegionToFrame(region, screenFrame))
		cleanup()

		if not confirm then
			return
		end

		hs.settings.set(SETTINGS_KEY, finalRegion)
		hs.timer.doAfter(CAPTURE_DELAY, function()
			onConfirm(finalRegion)
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
				local code = event:getKeyCode()
				if code == hs.keycodes.map.escape then
					finish(false)
					return true
				end
				if code == hs.keycodes.map["return"] or code == hs.keycodes.map.padenter then
					finish(region.w >= MIN_SIZE and region.h >= MIN_SIZE)
					return true
				end
				return true
			end

			local point = eventPoint(event)
			if eventType == eventTypes.leftMouseDown then
				if not frameContainsPoint(screenFrame, point) then
					finish(false)
					return true
				end

				local handle = handleAt(point, region)
				if handle then
					drag = {
						mode = "resize",
						handle = handle,
						startRegion = copyRect(region),
					}
				elseif pointInRect(point, region) then
					drag = {
						mode = "move",
						startPoint = point,
						startRegion = copyRect(region),
					}
				else
					drag = {
						mode = "new",
						anchor = point,
						moved = false,
					}
					updateNewRegion(point, point)
					redraw()
				end
				return true
			end

			if eventType == eventTypes.leftMouseDragged and drag then
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
					drag.moved = drag.moved or dx >= 3 or dy >= 3
					updateNewRegion(drag.anchor, point)
				end
				redraw()
				return true
			end

			if eventType == eventTypes.leftMouseUp then
				if drag and drag.mode == "new" and not drag.moved then
					finish(false)
				end
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
		cancel = function()
			finish(false)
		end,
	}
end

return M
