hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "V", nil, function()
	local paste_parts = os.getenv("HOME") .. "/bin/paste_parts"
	hs.task.new("/bin/bash", nil, { "-l", "-c", paste_parts }):start()
end)

-- Capture a selected screen region and upload it to Apollo via ~/bin/macscrot.
-- Run asynchronously so Hammerspoon does not block while the region is selected.
hs.hotkey.bind({ "ctrl", "alt", "shift" }, "s", nil, function()
	local macscrot = os.getenv("HOME") .. "/bin/macscrot"
	hs.task
		.new("/bin/bash", function(exitCode, stdOut, stdErr)
			local function tidy(text)
				return (tostring(text or ""):gsub("^%s+", ""):gsub("%s+$", ""))
			end
			if exitCode == 0 then
				hs.notify.show("Screenshot uploaded", "", tidy(stdOut))
			else
				hs.notify.show("Screenshot failed", "", tidy(stdErr))
			end
		end, { "-l", "-c", macscrot })
		:start()
end)

local taskCapturePrompt = nil
local taskCaptureController = nil
local taskCapturePreviousApp = nil

local taskCaptureHtml = [=[
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
	color-scheme: light dark;
	--background: #f7f7f8;
	--input: #ffffff;
	--text: #1d1d1f;
	--border: rgba(0, 0, 0, 0.15);
	--focus: #0a84ff;
	--button: #e9eaec;
}

@media (prefers-color-scheme: dark) {
	:root {
		--background: #18191b;
		--input: #222326;
		--text: #f5f5f7;
		--border: rgba(255, 255, 255, 0.16);
		--focus: #64d2ff;
		--button: #333438;
	}
}

* {
	box-sizing: border-box;
}

body {
	margin: 0;
	min-height: 100vh;
	background: var(--background);
	color: var(--text);
	font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
	font-size: 14px;
}

.shell {
	display: flex;
	min-height: 100vh;
	flex-direction: column;
	gap: 8px;
	padding: 12px 18px;
}

h1 {
	margin: 0;
	font-size: 15px;
	font-weight: 650;
	line-height: 1.25;
}

input {
	width: 100%;
	height: 30px;
	border: 1px solid var(--border);
	border-radius: 6px;
	background: var(--input);
	color: var(--text);
	font: inherit;
	outline: none;
	padding: 6px 9px;
	box-shadow: inset 0 1px 1px rgba(0, 0, 0, 0.02);
}

input:focus {
	border-color: var(--focus);
	box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.2);
}

footer {
	display: flex;
	align-items: center;
	justify-content: flex-end;
	gap: 10px;
}

button {
	min-width: 74px;
	border: 1px solid var(--border);
	border-radius: 6px;
	background: var(--button);
	color: var(--text);
	font: inherit;
	font-weight: 600;
	line-height: 1;
	padding: 8px 13px;
}

button.primary {
	border-color: transparent;
	background: var(--focus);
	color: white;
}

button:disabled {
	opacity: 0.45;
}
</style>
</head>
<body>
<main class="shell">
	<h1>Capture Task</h1>
	<input id="capture" type="text" aria-label="Task text" autocomplete="off" spellcheck="true">
	<footer>
		<button id="cancel" type="button">Cancel</button>
		<button id="add" type="button" class="primary" disabled>Add</button>
	</footer>
</main>
<script>
(() => {
	const input = document.getElementById("capture");
	const addButton = document.getElementById("add");
	const cancelButton = document.getElementById("cancel");

	function post(message) {
		try {
			webkit.messageHandlers.taskCapture.postMessage(message);
		} catch (error) {
			console.error(error);
		}
	}

	function updateAddState() {
		addButton.disabled = input.value.trim().length === 0;
	}

	function submit() {
		if (input.value.trim().length === 0) {
			return;
		}
		post({ action: "submit", text: input.value });
	}

	input.addEventListener("input", updateAddState);
	input.addEventListener("paste", (event) => {
		const pastedText = event.clipboardData ? event.clipboardData.getData("text") : "";
		if (!pastedText || !/[\r\n]/.test(pastedText)) {
			return;
		}

		event.preventDefault();
		const start = input.selectionStart == null ? input.value.length : input.selectionStart;
		const end = input.selectionEnd == null ? start : input.selectionEnd;
		input.setRangeText(pastedText.replace(/\s+/g, " "), start, end, "end");
		updateAddState();
	});
	input.addEventListener("keydown", (event) => {
		if (event.key === "Enter") {
			event.preventDefault();
			if (!event.shiftKey && !event.altKey && !event.ctrlKey && !event.metaKey) {
				submit();
			}
			return;
		}
	});

	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape") {
			event.preventDefault();
			post({ action: "cancel" });
		}
	});

	cancelButton.addEventListener("click", () => post({ action: "cancel" }));
	addButton.addEventListener("click", submit);

	window.addEventListener("load", () => {
		updateAddState();
		requestAnimationFrame(() => input.focus());
	});

	window.focusCaptureInput = () => {
		input.focus();
		updateAddState();
	};
})();
</script>
</body>
</html>
]=]

local function normalizeTaskText(rawText)
	local text = tostring(rawText or "")
	return text:gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", "")
end

local function capturedTaskCreatedProperty(now)
	if now then
		return os.date("[created::%Y-%m-%d]", now)
	end

	return os.date("[created::%Y-%m-%d]")
end

local function capturedTaskLine(taskText, now)
	return "- [ ] #task " .. taskText .. " " .. capturedTaskCreatedProperty(now)
end

local function routedCapturedTask(bobRoot, routeName, taskText)
	local normalizedRouteName = routeName:lower()
	return {
		target = bobRoot .. "/" .. normalizedRouteName .. ".md",
		text = taskText,
		isRouted = true,
		label = normalizedRouteName .. ".md",
	}
end

local function parseCapturedTaskTarget(text)
	local bobRoot = os.getenv("HOME") .. "/bob"

	local routeName, taskText = text:match("^@([A-Za-z0-9_-]+)%s+(.+)$")
	if routeName then
		return routedCapturedTask(bobRoot, routeName, taskText)
	end

	taskText, routeName = text:match("^(.+)%s+@([A-Za-z0-9_-]+)$")
	if routeName then
		return routedCapturedTask(bobRoot, routeName, taskText)
	end

	return {
		target = bobRoot .. "/mac_inbox.md",
		text = text,
		isRouted = false,
		label = "",
	}
end

local function readFile(path)
	local f, openError = io.open(path, "r")
	if not f then
		return nil, openError
	end

	local contents, readError = f:read("*a")
	local closeOk, closeError = f:close()
	if contents == nil or not closeOk then
		return nil, readError or closeError or path
	end

	return contents
end

local function writeFile(path, contents)
	local f, openError = io.open(path, "w")
	if not f then
		return false, openError
	end

	local writeOk, writeError = f:write(contents)
	local closeOk, closeError = f:close()
	if not writeOk or not closeOk then
		return false, writeError or closeError or path
	end

	return true
end

local function ensureFile(path)
	local f, openError = io.open(path, "a")
	if not f then
		return false, openError
	end

	local closeOk, closeError = f:close()
	if not closeOk then
		return false, closeError or path
	end

	return true
end

local function isIndentedTaskContinuation(line)
	return line:match("^[ \t]") ~= nil
end

local function isBlankMarkdownLine(line)
	return line:match("^%s*$") ~= nil
end

local function nextNonBlankLineIsIndented(contents, lineStart)
	while lineStart <= #contents do
		local newlineAt = contents:find("\n", lineStart, true)
		local line = newlineAt and contents:sub(lineStart, newlineAt - 1) or contents:sub(lineStart)
		if not isBlankMarkdownLine(line) then
			return isIndentedTaskContinuation(line)
		end
		if not newlineAt then
			return false
		end
		lineStart = newlineAt + 1
	end

	return false
end

local function taskBlockInsertionPoint(contents, taskLineStart)
	local lineStart = taskLineStart
	local newlineAt = contents:find("\n", lineStart, true)

	if not newlineAt then
		return #contents + 1, true, #contents + 1
	end

	local insertAt = newlineAt + 1
	lineStart = newlineAt + 1

	while lineStart <= #contents do
		newlineAt = contents:find("\n", lineStart, true)
		local line = newlineAt and contents:sub(lineStart, newlineAt - 1) or contents:sub(lineStart)
		local isTaskContinuation = isIndentedTaskContinuation(line)
			or (
				isBlankMarkdownLine(line)
				and newlineAt
				and nextNonBlankLineIsIndented(contents, newlineAt + 1)
			)
		if not isTaskContinuation then
			break
		end

		if not newlineAt then
			return #contents + 1, true, #contents + 1
		end

		insertAt = newlineAt + 1
		lineStart = newlineAt + 1
	end

	return insertAt, false, lineStart
end

local function insertTaskAfterLastOpenTask(path, taskLine)
	local ensureOk, ensureError = ensureFile(path)
	if not ensureOk then
		return false, ensureError
	end

	local contents, readError = readFile(path)
	if contents == nil then
		return false, readError
	end

	local insertAt = nil
	local needsLeadingNewline = false
	local lineStart = 1
	while lineStart <= #contents do
		local newlineAt = contents:find("\n", lineStart, true)
		local line = newlineAt and contents:sub(lineStart, newlineAt - 1) or contents:sub(lineStart)
		if line:match("^%- %[.%]%s+.*#task") then
			insertAt, needsLeadingNewline, lineStart = taskBlockInsertionPoint(contents, lineStart)
		else
			if not newlineAt then
				break
			end
			lineStart = newlineAt + 1
		end
	end

	local insertion = taskLine .. "\n"
	if needsLeadingNewline then
		insertion = "\n" .. insertion
	end

	local updatedContents
	if insertAt then
		updatedContents = contents:sub(1, insertAt - 1)
			.. insertion
			.. contents:sub(insertAt)
	else
		local separator = ""
		if contents ~= "" and contents:sub(-1) ~= "\n" then
			separator = "\n"
		end
		updatedContents = contents .. separator .. insertion
	end

	return writeFile(path, updatedContents)
end

local function appendCapturedTask(rawText, now)
	local text = normalizeTaskText(rawText)
	if text == "" then
		return true
	end

	local capturedTask = parseCapturedTaskTarget(text)
	local taskLine = capturedTaskLine(capturedTask.text, now)
	if capturedTask.isRouted then
		local insertOk, insertError = insertTaskAfterLastOpenTask(capturedTask.target, taskLine)
		if not insertOk then
			hs.notify.show("Task capture failed", "", insertError or capturedTask.target)
			return false
		end

		hs.notify.show("Captured task", capturedTask.label, capturedTask.text)
		return true
	end

	local target = capturedTask.target
	local f, openError = io.open(target, "a")
	if not f then
		hs.notify.show("Task capture failed", "", openError or target)
		return false
	end

	local writeOk, writeError = f:write(taskLine .. "\n")
	local closeOk, closeError = f:close()
	if not writeOk or not closeOk then
		hs.notify.show("Task capture failed", "", writeError or closeError or target)
		return false
	end

	hs.notify.show("Captured task", "", capturedTask.text)
	return true
end

local function restoreTaskCaptureApp()
	if taskCapturePreviousApp then
		pcall(function()
			taskCapturePreviousApp:activate()
		end)
		taskCapturePreviousApp = nil
	end
end

local function closeTaskCapturePrompt()
	local prompt = taskCapturePrompt
	taskCapturePrompt = nil
	taskCaptureController = nil
	if prompt then
		prompt:windowCallback(nil)
		prompt:delete()
	end

	restoreTaskCaptureApp()
end

local function taskCaptureFrame()
	local screen = nil
	local focusedWindow = hs.window.focusedWindow()
	if focusedWindow then
		screen = focusedWindow:screen()
	end
	screen = screen or hs.mouse.getCurrentScreen() or hs.screen.mainScreen()

	local frame = screen:frame()
	local width = math.min(560, frame.w - 80)
	local height = math.min(150, frame.h - 80)
	if width < 320 then
		width = math.min(320, frame.w)
	end
	if height < 130 then
		height = math.min(130, frame.h)
	end

	return {
		x = math.floor(frame.x + (frame.w - width) / 2),
		y = math.floor(frame.y + (frame.h - height) / 2),
		w = width,
		h = height,
	}
end

local function focusTaskCapturePrompt()
	if not taskCapturePrompt then
		return
	end

	taskCapturePrompt:show()
	taskCapturePrompt:bringToFront()

	local promptWindow = taskCapturePrompt:hswindow()
	if promptWindow then
		promptWindow:focus()
	end

	taskCapturePrompt:evaluateJavaScript(
		"if (window.focusCaptureInput) { window.focusCaptureInput(); }"
	)
end

local function showTaskCapturePrompt()
	if taskCapturePrompt then
		focusTaskCapturePrompt()
		return
	end

	taskCapturePreviousApp = hs.application.frontmostApplication()

	taskCaptureController = hs.webview.usercontent.new("taskCapture")
	taskCaptureController:setCallback(function(message)
		local payload = message
		if type(message) == "table" and type(message.body) == "table" then
			payload = message.body
		end
		if type(payload) ~= "table" then
			return
		end

		if payload.action == "cancel" then
			closeTaskCapturePrompt()
			return
		end

		if payload.action == "submit" and appendCapturedTask(payload.text) then
			closeTaskCapturePrompt()
		end
	end)

	taskCapturePrompt = hs.webview.new(
		taskCaptureFrame(),
		{ javaScriptCanOpenWindowsAutomatically = false },
		taskCaptureController
	)
	taskCapturePrompt:windowStyle({ "titled", "closable" })
	taskCapturePrompt:shadow(true)
	taskCapturePrompt:allowTextEntry(true)
	taskCapturePrompt:allowNewWindows(false)
	taskCapturePrompt:closeOnEscape(false)
	taskCapturePrompt:deleteOnClose(true)
	taskCapturePrompt:windowTitle("Capture Task")
	taskCapturePrompt:windowCallback(function(action, webview)
		if action == "closing" and webview == taskCapturePrompt then
			taskCapturePrompt = nil
			taskCaptureController = nil
			restoreTaskCaptureApp()
		end
	end)
	taskCapturePrompt:html(taskCaptureHtml)
	focusTaskCapturePrompt()
end

hs.hotkey.bind({ "cmd", "shift", "ctrl" }, "i", nil, function()
	showTaskCapturePrompt()
end)

BobPomodoroCountdown = BobPomodoroCountdown or {}
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

	local startHour, startMinute, endHour, endMinute =
		range:match("^(%d%d)(%d%d)%-(%d%d)(%d%d)$")
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

local function formatBobPomodoroSeconds(seconds)
	local sign = ""
	if seconds < 0 then
		sign = "+"
		seconds = -seconds
	end

	seconds = math.floor(seconds)
	return string.format("%s%d:%02d", sign, math.floor(seconds / 60), seconds % 60)
end

local bobPomodoroOverdueTitleAttributes = {
	color = { hex = "#ff453a", alpha = 1 },
	font = hs.styledtext.defaultFonts.menuBar,
}

local function bobPomodoroMenuTitle(seconds)
	local title = formatBobPomodoroSeconds(seconds)
	if seconds >= 0 then
		return title
	end

	return hs.styledtext.new(title, bobPomodoroOverdueTitleAttributes)
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

	local remaining = state.endEpoch - os.time()
	if remaining < -600 then
		hideBobPomodoroMenu()
		syncBobPomodoro()
		return
	end

	if remaining < 0
		and state.status == "active"
		and not state.zeroSyncRequested
	then
		state.zeroSyncRequested = true
		syncBobPomodoro()
	end

	menuBarItem:setTitle(bobPomodoroMenuTitle(remaining))
	menuBarItem:returnToMenuBar()
end

local bobPomodoroCommand = [[
PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH
if [ -z "${DATE+x}" ] && command -v gdate >/dev/null 2>&1; then
	export DATE=gdate
fi
exec bob pomodoro
]]

syncBobPomodoro = function()
	if bobPomodoroRuntime.task then
		return
	end

	local task
	task = hs.task.new("/bin/zsh", guardedBobPomodoroCallback("task completion", function(exitCode, stdOut, stdErr)
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
			hideBobPomodoroMenu()
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
	end), { "-lc", bobPomodoroCommand })

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
bobPomodoroRuntime.tickTimer = hs.timer.new(
	1,
	guardedBobPomodoroCallback("render timer", renderBobPomodoroMenu),
	true
):start()
bobPomodoroRuntime.syncTimer = hs.timer.new(
	15,
	guardedBobPomodoroCallback("sync timer", syncBobPomodoro),
	true
):start()
bobPomodoroRuntime.wakeWatcher = hs.caffeinate.watcher.new(guardedBobPomodoroCallback("wake watcher", function(eventType)
	if eventType == hs.caffeinate.watcher.systemDidWake
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
