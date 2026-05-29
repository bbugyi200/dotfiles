hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "V", nil, function()
	local paste_parts = os.getenv("HOME") .. "/bin/paste_parts"
	hs.task.new("/bin/bash", nil, { "-l", "-c", paste_parts }):start()
end)

local taskCapturePanel = nil
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
	--background: #f5f6f7;
	--surface: #ffffff;
	--text: #1d1d1f;
	--muted: #6e6e73;
	--border: rgba(0, 0, 0, 0.15);
	--focus: #0a84ff;
	--button: #e8eaed;
	--buttonText: #1d1d1f;
}

@media (prefers-color-scheme: dark) {
	:root {
		--background: #18191b;
		--surface: #222326;
		--text: #f5f5f7;
		--muted: #a1a1a6;
		--border: rgba(255, 255, 255, 0.16);
		--focus: #64d2ff;
		--button: #333438;
		--buttonText: #f5f5f7;
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
	font-size: 15px;
}

.shell {
	display: flex;
	min-height: 100vh;
	flex-direction: column;
	gap: 16px;
	padding: 22px;
}

header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 18px;
}

h1 {
	margin: 0;
	font-size: 18px;
	font-weight: 650;
	line-height: 1.25;
}

.destination {
	margin-top: 4px;
	color: var(--muted);
	font-size: 13px;
	line-height: 1.35;
}

.badge {
	flex: 0 0 auto;
	border: 1px solid var(--border);
	border-radius: 8px;
	color: var(--muted);
	font-size: 12px;
	font-weight: 600;
	line-height: 1;
	padding: 7px 9px;
}

textarea {
	flex: 1 1 auto;
	width: 100%;
	min-height: 0;
	resize: none;
	border: 1px solid var(--border);
	border-radius: 8px;
	background: var(--surface);
	color: var(--text);
	font: inherit;
	line-height: 1.5;
	outline: none;
	padding: 16px 17px;
	box-shadow: inset 0 1px 1px rgba(0, 0, 0, 0.02);
	transition: border-color 0.12s ease, box-shadow 0.12s ease;
}

textarea:focus {
	border-color: color-mix(in srgb, var(--focus) 78%, var(--border));
	box-shadow: 0 0 0 3px color-mix(in srgb, var(--focus) 22%, transparent);
}

footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
}

.hint {
	color: var(--muted);
	font-size: 12px;
	line-height: 1.3;
}

.actions {
	display: flex;
	align-items: center;
	gap: 10px;
}

button {
	min-width: 84px;
	border: 1px solid var(--border);
	border-radius: 8px;
	background: var(--button);
	color: var(--buttonText);
	font: inherit;
	font-size: 14px;
	font-weight: 600;
	line-height: 1;
	padding: 10px 14px;
	transition: background-color 0.12s ease, border-color 0.12s ease;
}

button:hover:not(:disabled) {
	border-color: color-mix(in srgb, var(--text) 24%, var(--border));
}

button:active:not(:disabled) {
	transform: translateY(1px);
}

button.primary {
	border-color: transparent;
	background: var(--focus);
	color: white;
}

button.primary:hover:not(:disabled) {
	background: color-mix(in srgb, var(--focus) 88%, black);
	border-color: transparent;
}

button.primary:active:not(:disabled) {
	background: color-mix(in srgb, var(--focus) 78%, black);
}

button:disabled {
	cursor: default;
	opacity: 0.45;
	transform: none;
}
</style>
</head>
<body>
<main class="shell">
	<header>
		<div>
			<h1>Capture Task</h1>
			<div class="destination">Bob inbox</div>
		</div>
		<div class="badge">mac_inbox.md</div>
	</header>
	<textarea id="capture" aria-label="Task text" spellcheck="true"></textarea>
	<footer>
		<div class="hint">Enter to add · Shift+Enter for a new line</div>
		<div class="actions">
			<button id="cancel" type="button">Cancel</button>
			<button id="add" type="button" class="primary" disabled>Add</button>
		</div>
	</footer>
</main>
<script>
(() => {
	const textarea = document.getElementById("capture");
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
		addButton.disabled = textarea.value.trim().length === 0;
	}

	function submit() {
		if (textarea.value.trim().length === 0) {
			return;
		}
		post({ action: "submit", text: textarea.value });
	}

	textarea.addEventListener("input", updateAddState);
	textarea.addEventListener("keydown", (event) => {
		if (event.key === "Enter") {
			if (event.shiftKey) {
				return;
			}
			event.preventDefault();
			submit();
			return;
		}
		if (event.key === "Escape") {
			event.preventDefault();
			post({ action: "cancel" });
		}
	});

	cancelButton.addEventListener("click", () => post({ action: "cancel" }));
	addButton.addEventListener("click", submit);

	window.addEventListener("load", () => {
		updateAddState();
		requestAnimationFrame(() => textarea.focus());
	});
})();
</script>
</body>
</html>
]=]

local function trimCaptureText(rawText)
	local text = tostring(rawText or "")
	text = text:gsub("\r\n", "\n"):gsub("\r", "\n")

	local lines = {}
	for line in (text .. "\n"):gmatch("(.-)\n") do
		table.insert(lines, line:gsub("%s+$", ""))
	end

	while #lines > 0 and lines[1]:match("^%s*$") do
		table.remove(lines, 1)
	end
	while #lines > 0 and lines[#lines]:match("^%s*$") do
		table.remove(lines)
	end

	return table.concat(lines, "\n")
end

local function captureMarkdownFromText(rawText)
	local text = trimCaptureText(rawText)
	if text == "" then
		return nil, nil
	end

	local title = nil
	local notes = {}
	for line in (text .. "\n"):gmatch("(.-)\n") do
		if line:match("%S") then
			if title == nil then
				title = line:gsub("^%s+", ""):gsub("%s+$", "")
			else
				table.insert(notes, line:gsub("%s+$", ""))
			end
		end
	end

	if title == nil or title == "" then
		return nil, nil
	end

	local markdown = "- [ ] #task " .. title .. "\n"
	for _, note in ipairs(notes) do
		markdown = markdown .. "  " .. note .. "\n"
	end

	return markdown, title
end

local function appendCapturedTask(rawText)
	local target = os.getenv("HOME") .. "/bob/mac_inbox.md"
	local markdown, summary = captureMarkdownFromText(rawText)
	if markdown == nil then
		return true
	end

	local f, openError = io.open(target, "a")
	if not f then
		hs.notify.show("Task capture failed", "", openError or target)
		return false
	end

	local writeOk, writeError = f:write(markdown)
	local closeOk, closeError = f:close()
	if not writeOk or not closeOk then
		hs.notify.show("Task capture failed", "", writeError or closeError or target)
		return false
	end

	hs.notify.show("Captured task", "", summary)
	return true
end

local function closeTaskCapturePanel()
	local panel = taskCapturePanel
	taskCapturePanel = nil
	taskCaptureController = nil
	if panel then
		panel:windowCallback(nil)
		panel:delete()
	end

	if taskCapturePreviousApp then
		taskCapturePreviousApp:activate()
		taskCapturePreviousApp = nil
	end
end

local function taskCaptureFrame()
	local screen = nil
	local focusedWindow = hs.window.focusedWindow()
	if focusedWindow then
		screen = focusedWindow:screen()
	end
	screen = screen or hs.mouse.getCurrentScreen() or hs.screen.mainScreen()

	local frame = screen:frame()
	local width = math.min(680, frame.w - 80)
	local height = math.min(430, frame.h - 80)

	return {
		x = math.floor(frame.x + (frame.w - width) / 2),
		y = math.floor(frame.y + (frame.h - height) / 2),
		w = width,
		h = height,
	}
end

local function focusTaskCapturePanel()
	if not taskCapturePanel then
		return
	end

	taskCapturePanel:show()
	taskCapturePanel:bringToFront()

	local panelWindow = taskCapturePanel:hswindow()
	if panelWindow then
		panelWindow:focus()
	end

	taskCapturePanel:evaluateJavaScript(
		"var capture = document.getElementById('capture'); if (capture) { capture.focus(); }"
	)
end

local function showTaskCapturePanel()
	if taskCapturePanel then
		focusTaskCapturePanel()
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
			closeTaskCapturePanel()
			return
		end

		if payload.action == "submit" and appendCapturedTask(payload.text) then
			closeTaskCapturePanel()
		end
	end)

	taskCapturePanel = hs.webview.new(
		taskCaptureFrame(),
		{ javaScriptCanOpenWindowsAutomatically = false },
		taskCaptureController
	)
	taskCapturePanel:windowStyle({ "titled", "closable" })
	taskCapturePanel:shadow(true)
	taskCapturePanel:allowTextEntry(true)
	taskCapturePanel:allowNewWindows(false)
	taskCapturePanel:closeOnEscape(false)
	taskCapturePanel:deleteOnClose(true)
	taskCapturePanel:windowTitle("Capture Task")
	taskCapturePanel:windowCallback(function(action, webview)
		if action == "closing" and webview == taskCapturePanel then
			taskCapturePanel = nil
			taskCaptureController = nil
		end
	end)
	taskCapturePanel:html(taskCaptureHtml)
	focusTaskCapturePanel()
end

hs.hotkey.bind({ "cmd", "shift", "ctrl" }, "i", nil, function()
	showTaskCapturePanel()
end)

-- Auto-reload the config whenever the deployed files change (e.g. after a
-- `chezmoi apply`), so edits take effect without a manual reload. The watcher
-- is retained in a module-level local to keep it from being garbage collected.
local configWatcher = hs.pathwatcher.new(os.getenv("HOME") .. "/.hammerspoon/", function()
	hs.reload()
end)
configWatcher:start()
