hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "V", nil, function()
	local paste_parts = os.getenv("HOME") .. "/bin/paste_parts"
	hs.task.new("/bin/bash", nil, { "-l", "-c", paste_parts }):start()
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

local function parseCapturedTaskTarget(text)
	local bobRoot = os.getenv("HOME") .. "/bob"
	local prefix, taskText = text:match("^([A-Za-z0-9_-]+):%s+(.+)$")
	if prefix then
		return {
			target = bobRoot .. "/" .. prefix .. ".md",
			text = taskText,
			isRouted = true,
			label = prefix .. ".md",
		}
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

local function insertTaskAfterLastOpenTask(path, taskLine)
	local ensureOk, ensureError = ensureFile(path)
	if not ensureOk then
		return false, ensureError
	end

	local contents, readError = readFile(path)
	if contents == nil then
		return false, readError
	end

	local taskPrefix = "- [ ] #task "
	local insertAt = nil
	local needsLeadingNewline = false
	local lineStart = 1
	while lineStart <= #contents do
		local newlineAt = contents:find("\n", lineStart, true)
		if contents:sub(lineStart, lineStart + #taskPrefix - 1) == taskPrefix then
			if newlineAt then
				insertAt = newlineAt + 1
				needsLeadingNewline = false
			else
				insertAt = #contents + 1
				needsLeadingNewline = true
			end
		end

		if not newlineAt then
			break
		end
		lineStart = newlineAt + 1
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

local function appendCapturedTask(rawText)
	local text = normalizeTaskText(rawText)
	if text == "" then
		return true
	end

	local capturedTask = parseCapturedTaskTarget(text)
	local taskLine = "- [ ] #task " .. capturedTask.text
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

-- Auto-reload the config whenever the deployed files change (e.g. after a
-- `chezmoi apply`), so edits take effect without a manual reload. The watcher
-- is retained in a module-level local to keep it from being garbage collected.
local configWatcher = hs.pathwatcher.new(os.getenv("HOME") .. "/.hammerspoon/", function()
	hs.reload()
end)
configWatcher:start()
