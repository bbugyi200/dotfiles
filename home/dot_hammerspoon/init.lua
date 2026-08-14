local PomodoroCountdown = require("pomodoro_countdown")
local ScreenshotRegion = require("screenshot_region")

hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "V", nil, function()
	local paste_parts = os.getenv("HOME") .. "/bin/paste_parts"
	hs.task.new("/bin/bash", nil, { "-l", "-c", paste_parts }):start()
end)

local function shellQuote(value)
	return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

local function runMacscrot(region)
	local macscrot = os.getenv("HOME") .. "/bin/macscrot"
	local command = shellQuote(macscrot)
	if region then
		command = command .. " " .. shellQuote(string.format("%d,%d,%d,%d", region.x, region.y, region.w, region.h))
	end

	hs.task
		.new("/bin/bash", function(exitCode, stdOut, stdErr)
			-- macscrot now owns the success notification for every invocation
			-- path, so only surface failures here to avoid a duplicate.
			if exitCode ~= 0 then
				local function tidy(text)
					return (tostring(text or ""):gsub("^%s+", ""):gsub("%s+$", ""))
				end
				local detail = tidy(stdErr)
				if detail == "" then
					detail = tidy(stdOut)
				end
				hs.notify.show("Screenshot failed", "", detail)
			end
		end, { "-l", "-c", command })
		:start()
end

-- Capture a selected screen region and upload it to Apollo via ~/bin/macscrot.
-- The selector preloads the last confirmed rectangle, then macscrot owns
-- capture, upload, clipboard, and success notification behavior.
hs.hotkey.bind({ "ctrl", "alt", "shift" }, "s", nil, function()
	ScreenshotRegion.pick(function(region)
		runMacscrot(region)
	end)
end)

if type(BobPomodoroCountdown) ~= "table" then
	BobPomodoroCountdown = {}
end

local bobPomodoroRuntime = BobPomodoroCountdown
local unpackArgs = table.unpack or unpack

local function stopBobPomodoroRuntimeObject(name, object)
	if not object then
		return
	end

	local ok, errorMessage = xpcall(function()
		if object.stop then
			object:stop()
		elseif object.terminate then
			object:terminate()
		end
	end, debug.traceback)
	if not ok then
		hs.printf("Bob Pomodoro could not stop previous %s: %s", name, errorMessage)
	end
end

stopBobPomodoroRuntimeObject("tick timer", bobPomodoroRuntime.tickTimer)
stopBobPomodoroRuntimeObject("sync timer", bobPomodoroRuntime.syncTimer)
stopBobPomodoroRuntimeObject("wake watcher", bobPomodoroRuntime.wakeWatcher)
stopBobPomodoroRuntimeObject("task", bobPomodoroRuntime.task)

bobPomodoroRuntime.menu = bobPomodoroRuntime.menu or hs.menubar.new(false)
bobPomodoroRuntime.task = nil
bobPomodoroRuntime.state = nil
bobPomodoroRuntime.tickTimer = nil
bobPomodoroRuntime.syncTimer = nil
bobPomodoroRuntime.wakeWatcher = nil

local function clearBobPomodoroMenu(menu)
	if not menu then
		return
	end

	menu:setTitle("")
	menu:setTooltip("")
	menu:setMenu({})
	menu:removeFromMenuBar()
end

local function handleBobPomodoroCallbackError(context, errorMessage)
	bobPomodoroRuntime.state = nil
	local ok, clearError = xpcall(function()
		clearBobPomodoroMenu(bobPomodoroRuntime.menu)
	end, debug.traceback)
	if not ok then
		hs.printf("Bob Pomodoro could not clear menu after %s failure: %s", context, clearError)
	end

	hs.printf("Bob Pomodoro %s failed: %s", context, errorMessage)
end

local function runBobPomodoroCallback(context, callback, ...)
	local args = { n = select("#", ...), ... }
	local ok, result = xpcall(function()
		return callback(unpackArgs(args, 1, args.n))
	end, debug.traceback)
	if not ok then
		handleBobPomodoroCallbackError(context, result)
	end

	return ok, result
end

local function guardedBobPomodoroCallback(context, callback)
	return function(...)
		runBobPomodoroCallback(context, callback, ...)
	end
end

local function trimText(rawText)
	local text = tostring(rawText or "")
	text = text:gsub("^%s+", "")
	text = text:gsub("%s+$", "")
	return text
end

local function parseBobPomodoroOutput(rawOutput)
	local output = trimText(rawOutput)
	if output == "" then
		return nil
	end

	local status = "active"
	local body = output
	if body:match("^%[OVERDUE by %d+m%]%s+") then
		status = "overdue"
		body = body:gsub("^%[OVERDUE by %d+m%]%s+", "")
	elseif body:match("^%[<%d+m%]%s+") then
		body = body:gsub("^%[<%d+m%]%s+", "")
	end

	local range, taskText = body:match("^(%d%d%d%d%-%d%d%d%d)%s*(.*)$")
	if not range then
		return nil, "missing normalized HHMM-HHMM range"
	end

	local startHour, startMinute, endHour, endMinute = range:match("^(%d%d)(%d%d)%-(%d%d)(%d%d)$")
	startHour = tonumber(startHour)
	startMinute = tonumber(startMinute)
	endHour = tonumber(endHour)
	endMinute = tonumber(endMinute)
	if startHour > 23 or startMinute > 59 or endHour > 23 or endMinute > 59 then
		return nil, "invalid normalized HHMM-HHMM range"
	end

	return {
		rawOutput = output,
		range = range,
		taskText = trimText(taskText),
		status = status,
		endHour = endHour,
		endMinute = endMinute,
	}
end

local function todayEndEpoch(endHour, endMinute)
	local today = os.date("*t")
	today.hour = endHour
	today.min = endMinute
	today.sec = 0
	today.isdst = nil
	return os.time(today)
end

local bobPomodoroMenuBarFont = hs.styledtext.defaultFonts.menuBar

local bobPomodoroOverdueTitleAttributes = {
	color = { hex = "#ff453a", alpha = 1 },
	font = bobPomodoroMenuBarFont,
}

local function validBobPomodoroFont(font)
	if type(font) ~= "table" or type(font.name) ~= "string" or font.name == "" then
		return nil
	end
	if type(hs.styledtext.validFont) ~= "function" or not hs.styledtext.validFont(font.name) then
		return nil
	end
	return font
end

local function bobPomodoroFontWithMenuBarSize(fontName)
	local font = { name = fontName }
	if type(bobPomodoroMenuBarFont) == "table" and bobPomodoroMenuBarFont.size then
		font.size = bobPomodoroMenuBarFont.size
	end
	return font
end

local function resolveBobPomodoroBoldMenuBarFont()
	local convertedFont = hs.styledtext.convertFont(bobPomodoroMenuBarFont, hs.styledtext.fontTraits.boldFont)
	local validConvertedFont = validBobPomodoroFont(convertedFont)
	if validConvertedFont then
		return validConvertedFont
	end

	for _, fallbackName in ipairs({ "Helvetica-Bold", "HelveticaNeue-Bold", "Arial-BoldMT" }) do
		local fallbackFont = validBobPomodoroFont(bobPomodoroFontWithMenuBarSize(fallbackName))
		if fallbackFont then
			return fallbackFont
		end
	end

	return nil
end

local function bobPomodoroTitleAttributes(color, font)
	local attributes = {
		color = color,
	}
	if font then
		attributes.font = font
	end
	return attributes
end

local bobPomodoroBoldMenuBarFont = resolveBobPomodoroBoldMenuBarFont()

local bobPomodoroMissingTitleAttributes =
	bobPomodoroTitleAttributes({ hex = "#30d158", alpha = 1 }, bobPomodoroBoldMenuBarFont)

local bobPomodoroOverdueWarningTitleAttributes =
	bobPomodoroTitleAttributes({ hex = "#ff453a", alpha = 1 }, bobPomodoroBoldMenuBarFont)

local function bobPomodoroMenuTitle(presentation)
	if presentation.appearance == "normal" then
		return presentation.title
	end
	if presentation.appearance == "overdue" then
		return hs.styledtext.new(presentation.title, bobPomodoroOverdueTitleAttributes)
	end
	if presentation.appearance == "missing" then
		return hs.styledtext.new(presentation.title, bobPomodoroMissingTitleAttributes)
	end
	if presentation.appearance == "overdue_warning" then
		return hs.styledtext.new(presentation.title, bobPomodoroOverdueWarningTitleAttributes)
	end

	return presentation.title
end

local syncBobPomodoro

local function hideBobPomodoroMenu()
	bobPomodoroRuntime.state = nil
	clearBobPomodoroMenu(bobPomodoroRuntime.menu)
end

local function updateBobPomodoroMenuDetails()
	local menuBarItem = bobPomodoroRuntime.menu
	local state = bobPomodoroRuntime.state
	if not menuBarItem or not state then
		return
	end

	local menu = {
		{ title = state.rawOutput, disabled = true },
		{
			title = "Last sync " .. os.date("%H:%M:%S", state.lastSyncEpoch),
			disabled = true,
		},
		{ title = "-" },
		{
			title = "Refresh",
			fn = function()
				runBobPomodoroCallback("manual refresh", syncBobPomodoro)
			end,
		},
	}

	menuBarItem:setTooltip(state.rawOutput)
	menuBarItem:setMenu(menu)
end

local function renderBobPomodoroMenu()
	local menuBarItem = bobPomodoroRuntime.menu
	local state = bobPomodoroRuntime.state
	if not menuBarItem or not state then
		if menuBarItem then
			menuBarItem:removeFromMenuBar()
		end
		return
	end

	local remaining = state.endEpoch and state.endEpoch - os.time() or nil

	if remaining and remaining < 0 and state.status == "active" and not state.zeroSyncRequested then
		state.zeroSyncRequested = true
		syncBobPomodoro()
	end

	local presentation = PomodoroCountdown.presentation(remaining)
	menuBarItem:setTitle(bobPomodoroMenuTitle(presentation))
	menuBarItem:returnToMenuBar()
end

local bobPomodoroCommand = [[
PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH
if [ -z "${DATE+x}" ] && command -v gdate >/dev/null 2>&1; then
	export DATE=gdate
fi
exec bob pomodoro --show-stale
]]

syncBobPomodoro = function()
	if bobPomodoroRuntime.task then
		return
	end

	local task
	task = hs.task.new(
		"/bin/zsh",
		guardedBobPomodoroCallback("task completion", function(exitCode, stdOut, stdErr)
			if bobPomodoroRuntime.task ~= task then
				return
			end
			bobPomodoroRuntime.task = nil

			if exitCode ~= 0 then
				hideBobPomodoroMenu()
				hs.printf("bob pomodoro failed with exit code %s: %s", exitCode, trimText(stdErr))
				return
			end

			local output = trimText(stdOut)
			if output == "" then
				bobPomodoroRuntime.state = {
					rawOutput = "No current Pomodoro",
					status = "missing",
					lastSyncEpoch = os.time(),
				}
				updateBobPomodoroMenuDetails()
				renderBobPomodoroMenu()
				return
			end

			local parsed, parseError = parseBobPomodoroOutput(output)
			if not parsed then
				hideBobPomodoroMenu()
				hs.printf("bob pomodoro output could not be parsed: %s: %s", parseError, output)
				return
			end

			parsed.endEpoch = todayEndEpoch(parsed.endHour, parsed.endMinute)
			parsed.lastSyncEpoch = os.time()
			bobPomodoroRuntime.state = parsed
			updateBobPomodoroMenuDetails()
			renderBobPomodoroMenu()
		end),
		{ "-lc", bobPomodoroCommand }
	)

	if not task then
		hideBobPomodoroMenu()
		hs.printf("bob pomodoro task could not be created")
		return
	end

	bobPomodoroRuntime.task = task
	local startOk, startedOrError = xpcall(function()
		return task:start()
	end, debug.traceback)
	if not startOk or not startedOrError then
		bobPomodoroRuntime.task = nil
		hideBobPomodoroMenu()
		if startOk then
			hs.printf("bob pomodoro task could not be started")
		else
			hs.printf("bob pomodoro task start failed: %s", startedOrError)
		end
	end
end

hideBobPomodoroMenu()
bobPomodoroRuntime.tickTimer =
	hs.timer.new(1, guardedBobPomodoroCallback("render timer", renderBobPomodoroMenu), true):start()
bobPomodoroRuntime.syncTimer = hs.timer.new(15, guardedBobPomodoroCallback("sync timer", syncBobPomodoro), true):start()
bobPomodoroRuntime.wakeWatcher =
	hs.caffeinate.watcher.new(guardedBobPomodoroCallback("wake watcher", function(eventType)
		if
			eventType == hs.caffeinate.watcher.systemDidWake
			or eventType == hs.caffeinate.watcher.screensDidWake
			or eventType == hs.caffeinate.watcher.screensDidUnlock
		then
			syncBobPomodoro()
		end
	end))
bobPomodoroRuntime.wakeWatcher:start()
runBobPomodoroCallback("initial sync", syncBobPomodoro)

-- Auto-reload the config whenever the deployed files change (e.g. after a
-- `chezmoi apply`), so edits take effect without a manual reload. The watcher
-- is retained in a module-level local to keep it from being garbage collected.
local configWatcher = hs.pathwatcher.new(os.getenv("HOME") .. "/.hammerspoon/", function()
	hs.reload()
end)
configWatcher:start()
