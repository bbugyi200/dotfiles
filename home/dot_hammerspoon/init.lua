local PingIndicator = require("ping_indicator")
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

-- Capture a selected screen region and upload it to Apollo and Athena via ~/bin/macscrot.
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
local BOB_POMODORO_TICK_INTERVAL = 0.5 -- Flash half-period for the OVERDUE badge and the NO POMODORO reminder.
local BOB_POMODORO_POLL_INTERVAL = 60 -- Safety net while the vault watcher runs.
local BOB_POMODORO_FALLBACK_POLL_INTERVAL = 15 -- Used when the vault watcher is unavailable.
-- Hammerspoon does not inherit shell BOB_DIR; the vault-sync LaunchAgent uses ~/bob.
local BOB_POMODORO_VAULT_ROOT = os.getenv("HOME") .. "/bob"
local bobPomodoroFlashOn = false

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
stopBobPomodoroRuntimeObject("vault watcher", bobPomodoroRuntime.vaultWatcher)
stopBobPomodoroRuntimeObject("vault debounce", bobPomodoroRuntime.vaultChangeDebounce)
stopBobPomodoroRuntimeObject("task", bobPomodoroRuntime.task)

bobPomodoroRuntime.menu = bobPomodoroRuntime.menu or hs.menubar.new(false)
bobPomodoroRuntime.task = nil
bobPomodoroRuntime.state = nil
bobPomodoroRuntime.tickTimer = nil
bobPomodoroRuntime.syncTimer = nil
bobPomodoroRuntime.wakeWatcher = nil
bobPomodoroRuntime.vaultWatcher = nil
bobPomodoroRuntime.vaultChangeDebounce = nil
bobPomodoroRuntime.resyncRequested = false

local function clearBobPomodoroMenu(menu)
	if not menu then
		return
	end

	menu:setTitle("")
	menu:setTooltip("")
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
		startHour = startHour,
		startMinute = startMinute,
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

local bobPomodoroContextForeground = { list = "System", name = "labelColor", alpha = 1 }
local bobPomodoroOverdueForeground = { hex = PomodoroCountdown.ALERT_COLOR, alpha = 1 }

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

local function bobPomodoroTitleAttributes(color, font, backgroundColor)
	local attributes = {
		color = color,
	}
	if font then
		attributes.font = font
	end
	if backgroundColor then
		attributes.backgroundColor = backgroundColor
	end
	return attributes
end

local function resolveBobPomodoroMonoMenuBarFont()
	for _, fallbackName in ipairs({ "Menlo-Regular", "Menlo", "Monaco" }) do
		local fallbackFont = validBobPomodoroFont(bobPomodoroFontWithMenuBarSize(fallbackName))
		if fallbackFont then
			return fallbackFont
		end
	end

	return nil
end

local function resolveBobPomodoroMonoBoldMenuBarFont()
	return validBobPomodoroFont(bobPomodoroFontWithMenuBarSize("Menlo-Bold"))
end

local bobPomodoroBoldMenuBarFont = resolveBobPomodoroBoldMenuBarFont()
local bobPomodoroMonoMenuBarFont = resolveBobPomodoroMonoMenuBarFont() or bobPomodoroMenuBarFont
local bobPomodoroMonoBoldMenuBarFont = resolveBobPomodoroMonoBoldMenuBarFont()
local bobPomodoroCountdownFont = bobPomodoroMonoBoldMenuBarFont or bobPomodoroMonoMenuBarFont

local bobPomodoroIconTitleAttributes = bobPomodoroTitleAttributes(bobPomodoroContextForeground, bobPomodoroMenuBarFont)

local bobPomodoroMissingTitleAttributes =
	bobPomodoroTitleAttributes({ hex = PomodoroCountdown.MISSING_COLOR, alpha = 1 }, bobPomodoroBoldMenuBarFont)
local bobPomodoroMissingFlashTitleAttributes = bobPomodoroTitleAttributes(
	{ hex = PomodoroCountdown.MISSING_BADGE_TEXT_COLOR, alpha = 1 },
	bobPomodoroBoldMenuBarFont,
	{ hex = PomodoroCountdown.MISSING_COLOR, alpha = 1 }
)
local bobPomodoroMissingPhiTitleAttributes =
	bobPomodoroTitleAttributes({ hex = PomodoroCountdown.MISSING_COLOR, alpha = 1 }, bobPomodoroMenuBarFont)
local bobPomodoroMissingPhiFlashTitleAttributes = bobPomodoroTitleAttributes(
	{ hex = PomodoroCountdown.MISSING_BADGE_TEXT_COLOR, alpha = 1 },
	bobPomodoroMenuBarFont,
	{ hex = PomodoroCountdown.MISSING_COLOR, alpha = 1 }
)

local bobPomodoroThemeTitleAttributes =
	bobPomodoroTitleAttributes(bobPomodoroContextForeground, bobPomodoroBoldMenuBarFont or bobPomodoroMenuBarFont)
local bobPomodoroContextTitleAttributes =
	bobPomodoroTitleAttributes(bobPomodoroContextForeground, bobPomodoroMenuBarFont)
local bobPomodoroStopTitleAttributes =
	bobPomodoroTitleAttributes(bobPomodoroContextForeground, bobPomodoroMonoMenuBarFont)
local bobPomodoroCountdownTitleAttributes =
	bobPomodoroTitleAttributes(bobPomodoroContextForeground, bobPomodoroCountdownFont)
local bobPomodoroOverdueCountdownTitleAttributes =
	bobPomodoroTitleAttributes(bobPomodoroOverdueForeground, bobPomodoroCountdownFont)

local bobPomodoroOverdueWarningTitleAttributes =
	bobPomodoroTitleAttributes({ hex = PomodoroCountdown.ALERT_COLOR, alpha = 1 }, bobPomodoroBoldMenuBarFont)
local bobPomodoroOverdueWarningFlashTitleAttributes = bobPomodoroTitleAttributes(
	{ hex = PomodoroCountdown.BADGE_TEXT_COLOR, alpha = 1 },
	bobPomodoroBoldMenuBarFont,
	{ hex = PomodoroCountdown.ALERT_COLOR, alpha = 1 }
)

local bobPomodoroNoBreakSpace = "\194\160"

local function bobPomodoroSegmentText(segments, role)
	if type(segments) ~= "table" then
		return nil
	end
	for _, segment in ipairs(segments) do
		if type(segment) == "table" and segment.role == role then
			return tostring(segment.text or "")
		end
	end
	return nil
end

local function bobPomodoroMenuTitle(presentation)
	if type(presentation) ~= "table" or type(presentation.title) ~= "string" then
		return ""
	end

	local ok, composed = pcall(function()
		if type(presentation.segments) ~= "table" then
			error("missing segments")
		end

		local appearance = presentation.appearance
		local is_missing = appearance == "missing" or appearance == "missing_flash"
		if
			not is_missing
			and appearance ~= "normal"
			and appearance ~= "overdue"
			and appearance ~= "overdue_warning"
			and appearance ~= "overdue_warning_flash"
		then
			error("unknown appearance: " .. tostring(appearance))
		end

		local has_theme = false
		local has_status = false
		local has_missing = false
		for _, segment in ipairs(presentation.segments) do
			if type(segment) == "table" then
				if segment.role == "theme" then
					has_theme = true
				elseif segment.role == "status" then
					has_status = true
				elseif segment.role == "missing" then
					has_missing = true
				end
			end
		end
		if is_missing then
			assert(has_missing, "missing missing segment")
		else
			assert(has_theme, "missing theme segment")
			assert(has_status, "missing status segment")
		end

		local composed_title = nil
		local segment_count = #presentation.segments
		for index, segment in ipairs(presentation.segments) do
			if type(segment) ~= "table" or type(segment.text) ~= "string" then
				error("invalid segment")
			end
			local text = segment.text
			local attributes = nil
			if segment.role == "icon" then
				attributes = bobPomodoroIconTitleAttributes
			elseif segment.role == "gap" then
				attributes = bobPomodoroContextTitleAttributes
			elseif segment.role == "theme" then
				attributes = bobPomodoroThemeTitleAttributes
			elseif segment.role == "duration" then
				attributes = bobPomodoroContextTitleAttributes
			elseif segment.role == "arrow" then
				attributes = bobPomodoroContextTitleAttributes
			elseif segment.role == "stop" then
				attributes = bobPomodoroStopTitleAttributes
			elseif segment.role == "separator" then
				attributes = bobPomodoroContextTitleAttributes
			elseif segment.role == "status" then
				if appearance == "normal" then
					attributes = bobPomodoroCountdownTitleAttributes
				elseif appearance == "overdue" then
					attributes = bobPomodoroOverdueCountdownTitleAttributes
				elseif appearance == "overdue_warning" then
					text = bobPomodoroNoBreakSpace .. text .. bobPomodoroNoBreakSpace
					attributes = bobPomodoroOverdueWarningTitleAttributes
				elseif appearance == "overdue_warning_flash" then
					text = bobPomodoroNoBreakSpace .. text .. bobPomodoroNoBreakSpace
					attributes = bobPomodoroOverdueWarningFlashTitleAttributes
				else
					error("unknown appearance: " .. tostring(appearance))
				end
			elseif segment.role == "missing" then
				text = bobPomodoroNoBreakSpace .. text
				if appearance == "missing_flash" then
					attributes = bobPomodoroMissingFlashTitleAttributes
				elseif appearance == "missing" then
					attributes = bobPomodoroMissingTitleAttributes
				else
					error("unknown appearance: " .. tostring(appearance))
				end
			elseif segment.role == "phi" then
				if appearance == "missing_flash" then
					attributes = bobPomodoroMissingPhiFlashTitleAttributes
				elseif appearance == "missing" then
					attributes = bobPomodoroMissingPhiTitleAttributes
				else
					error("unknown segment role: " .. tostring(segment.role))
				end
			elseif segment.role == "waited" then
				if appearance == "missing_flash" then
					attributes = bobPomodoroMissingFlashTitleAttributes
				elseif appearance == "missing" then
					attributes = bobPomodoroMissingTitleAttributes
				else
					error("unknown segment role: " .. tostring(segment.role))
				end
			else
				error("unknown segment role: " .. tostring(segment.role))
			end
			if is_missing and index == segment_count then
				text = text .. bobPomodoroNoBreakSpace
			end

			local styled = hs.styledtext.new(text, attributes)
			if composed_title == nil then
				composed_title = styled
			else
				composed_title = composed_title .. styled
			end
		end

		if composed_title == nil then
			error("empty segments")
		end
		return composed_title
	end)

	if ok and composed ~= nil then
		return composed
	end
	return presentation.title
end

local syncBobPomodoro
local requestBobPomodoroResync

local function bobPomodoroMissingShownEpoch(previousState, now)
	if
		type(previousState) == "table"
		and previousState.status == "missing"
		and type(previousState.missingShownEpoch) == "number"
		and previousState.missingShownEpoch <= now
	then
		return previousState.missingShownEpoch
	end
	return now
end

local function hideBobPomodoroMenu()
	bobPomodoroRuntime.state = nil
	clearBobPomodoroMenu(bobPomodoroRuntime.menu)
end

local function buildBobPomodoroMenuItems()
	local state = bobPomodoroRuntime.state
	if not state then
		return {}
	end

	if state.fullTheme ~= nil and state.stopTime ~= nil then
		local theme_label = state.fullTheme
		if state.duration ~= nil and tostring(state.duration) ~= "" then
			theme_label = theme_label .. " (" .. tostring(state.duration) .. ")"
		end
		return {
			{ title = theme_label .. " → " .. state.stopTime, disabled = true },
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
	end
	local items = {
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
	if type(state.missingShownEpoch) == "number" then
		local next_step = PomodoroCountdown.next_missing_reminder(os.time() - state.missingShownEpoch)
		if next_step ~= nil then
			local waited = PomodoroCountdown.format_duration(next_step.waitMinutes)
			if waited ~= nil then
				local next_title = "Next reminder at "
					.. os.date("%H:%M", state.missingShownEpoch + next_step.startSeconds)
					.. " · "
					.. PomodoroCountdown.PHI
					.. " "
					.. waited
				table.insert(items, 2, { title = next_title, disabled = true })
			end
		end
	end
	return items
end

local function updateBobPomodoroTooltip()
	local menuBarItem = bobPomodoroRuntime.menu
	local state = bobPomodoroRuntime.state
	if not menuBarItem or not state then
		return
	end

	local tooltip = state.rawOutput
	if state.fullTheme ~= nil and state.stopTime ~= nil then
		local theme_label = state.fullTheme
		if state.duration ~= nil and tostring(state.duration) ~= "" then
			theme_label = theme_label .. " (" .. tostring(state.duration) .. ")"
		end
		tooltip = theme_label .. "\nStops at " .. state.stopTime .. "\n" .. state.rawOutput
	end

	menuBarItem:setTooltip(tooltip)
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

	local context = nil
	if state.status ~= "missing" then
		context = {
			theme = state.fullTheme or state.taskText,
			stop = state.stopTime,
			endHour = state.endHour,
			endMinute = state.endMinute,
			duration = state.duration,
			durationMinutes = state.durationMinutes,
		}
	elseif type(state.missingShownEpoch) == "number" then
		context = { missingShownSeconds = os.time() - state.missingShownEpoch }
	end

	local presentation = PomodoroCountdown.presentation(remaining, bobPomodoroFlashOn, context)
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
			local followUpRequested = bobPomodoroRuntime.resyncRequested
			bobPomodoroRuntime.resyncRequested = false

			if exitCode ~= 0 then
				hideBobPomodoroMenu()
				hs.printf("bob pomodoro failed with exit code %s: %s", exitCode, trimText(stdErr))
				if followUpRequested then
					syncBobPomodoro()
				end
				return
			end

			local output = trimText(stdOut)
			if output == "" then
				local now = os.time()
				local previousState = bobPomodoroRuntime.state
				bobPomodoroRuntime.state = {
					rawOutput = "No current Pomodoro",
					status = "missing",
					lastSyncEpoch = now,
					missingShownEpoch = bobPomodoroMissingShownEpoch(previousState, now),
				}
				updateBobPomodoroTooltip()
				renderBobPomodoroMenu()
				if followUpRequested then
					syncBobPomodoro()
				end
				return
			end

			local parsed, parseError = parseBobPomodoroOutput(output)
			if not parsed then
				hideBobPomodoroMenu()
				hs.printf("bob pomodoro output could not be parsed: %s: %s", parseError, output)
				if followUpRequested then
					syncBobPomodoro()
				end
				return
			end

			parsed.fullTheme = PomodoroCountdown.normalize_theme(parsed.taskText)
			parsed.displayTheme = PomodoroCountdown.shorten_theme(parsed.fullTheme)
			parsed.stopTime = PomodoroCountdown.format_stop_time(parsed.endHour, parsed.endMinute)
			parsed.endEpoch = todayEndEpoch(parsed.endHour, parsed.endMinute)
			parsed.durationMinutes = PomodoroCountdown.duration_minutes(
				parsed.startHour,
				parsed.startMinute,
				parsed.endHour,
				parsed.endMinute
			)
			parsed.duration = PomodoroCountdown.format_duration(parsed.durationMinutes)
			parsed.lastSyncEpoch = os.time()
			bobPomodoroRuntime.state = parsed
			updateBobPomodoroTooltip()
			renderBobPomodoroMenu()
			if followUpRequested then
				syncBobPomodoro()
			end
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
		bobPomodoroRuntime.resyncRequested = false
		hideBobPomodoroMenu()
		if startOk then
			hs.printf("bob pomodoro task could not be started")
		else
			hs.printf("bob pomodoro task start failed: %s", startedOrError)
		end
	end
end

requestBobPomodoroResync = function()
	if bobPomodoroRuntime.task then
		bobPomodoroRuntime.resyncRequested = true
	else
		syncBobPomodoro()
	end
end

-- Install the lazy builder once per config load, never from a sync, tick, or
-- hide path. Calling setMenu while the menu is open empties and detaches the
-- open NSMenu (which closes the dropdown), and timers keep firing while a menu
-- is open. Hammerspoon keeps the same NSMenu and delegate across
-- removeFromMenuBar / returnToMenuBar, so the builder survives hide and show.
bobPomodoroRuntime.menu:setMenu(function()
	local ok, items = xpcall(buildBobPomodoroMenuItems, debug.traceback)
	if not ok then
		hs.printf("Bob Pomodoro menu failed: %s", items)
		return {}
	end
	return items
end)
hideBobPomodoroMenu()
bobPomodoroRuntime.tickTimer = hs.timer
	.new(
		BOB_POMODORO_TICK_INTERVAL,
		guardedBobPomodoroCallback("render timer", function()
			bobPomodoroFlashOn = not bobPomodoroFlashOn
			renderBobPomodoroMenu()
		end),
		true
	)
	:start()

local function bobPomodoroVaultChangeMatchesDayFile(paths)
	local suffix = "/" .. os.date("%Y") .. "/" .. os.date("%Y%m%d") .. ".md"
	if type(paths) ~= "table" then
		return false
	end
	for _, path in ipairs(paths) do
		if type(path) == "string" and #path >= #suffix and path:sub(-#suffix) == suffix then
			return true
		end
	end
	return false
end

local vaultStartOk, vaultStartError = xpcall(function()
	bobPomodoroRuntime.vaultChangeDebounce =
		hs.timer.delayed.new(0.25, guardedBobPomodoroCallback("vault watcher sync", requestBobPomodoroResync))
	local watcher = hs.pathwatcher.new(
		BOB_POMODORO_VAULT_ROOT,
		guardedBobPomodoroCallback("vault watcher", function(paths, _flagTables)
			if bobPomodoroVaultChangeMatchesDayFile(paths) then
				bobPomodoroRuntime.vaultChangeDebounce:start()
			end
		end)
	)
	if watcher == nil then
		error("hs.pathwatcher.new returned nil")
	end
	watcher:start()
	bobPomodoroRuntime.vaultWatcher = watcher
end, debug.traceback)
if not vaultStartOk then
	bobPomodoroRuntime.vaultWatcher = nil
	hs.printf("Bob Pomodoro vault watcher unavailable: %s", vaultStartError)
end

local bobPomodoroPollInterval = BOB_POMODORO_POLL_INTERVAL
if bobPomodoroRuntime.vaultWatcher == nil then
	bobPomodoroPollInterval = BOB_POMODORO_FALLBACK_POLL_INTERVAL
end
bobPomodoroRuntime.syncTimer =
	hs.timer.new(bobPomodoroPollInterval, guardedBobPomodoroCallback("sync timer", syncBobPomodoro), true):start()
bobPomodoroRuntime.wakeWatcher =
	hs.caffeinate.watcher.new(guardedBobPomodoroCallback("wake watcher", function(eventType)
		if
			eventType == hs.caffeinate.watcher.systemDidWake
			or eventType == hs.caffeinate.watcher.screensDidWake
			or eventType == hs.caffeinate.watcher.screensDidUnlock
		then
			local state = bobPomodoroRuntime.state
			if type(state) == "table" and state.status == "missing" then
				state.missingShownEpoch = os.time()
			end
			syncBobPomodoro()
		end
	end))
bobPomodoroRuntime.wakeWatcher:start()
runBobPomodoroCallback("initial sync", syncBobPomodoro)

-- Internet ping menu bar. A ping failure must never break the hotkeys, the
-- Pomodoro item, or auto-reload, so a throwing start is logged and swallowed.
local pingStartOk, pingStartError = xpcall(function()
	PingIndicator.start()
end, debug.traceback)
if not pingStartOk then
	hs.printf("Bob ping start failed: %s", pingStartError)
end

-- Auto-reload the config whenever the deployed files change (e.g. after a
-- `chezmoi apply`), so edits take effect without a manual reload. The watcher
-- is retained in a module-level local to keep it from being garbage collected.
local configWatcher = hs.pathwatcher.new(os.getenv("HOME") .. "/.hammerspoon/", function()
	hs.reload()
end)
configWatcher:start()
