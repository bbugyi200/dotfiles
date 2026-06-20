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
		end, { "-l", "-c", macscrot })
		:start()
end)

local taskCapturePrompt = nil
local taskCaptureController = nil
local taskCapturePreviousApp = nil
local taskCaptureTask = nil
local taskCaptureChooser = nil

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

local function restoreTaskCaptureApp()
	if taskCapturePreviousApp then
		pcall(function()
			taskCapturePreviousApp:activate()
		end)
		taskCapturePreviousApp = nil
	end
end

-- Terminate any in-flight `bob` task so a late callback cannot act on a prompt
-- that has already been dismissed.
local function cancelTaskCaptureTask()
	local task = taskCaptureTask
	taskCaptureTask = nil
	if task then
		pcall(function()
			task:terminate()
		end)
	end
end

-- Tear down any open target picker. The module variable is cleared before the
-- chooser is deleted so that the chooser's own dismissal callback, which is
-- guarded by object identity, becomes a no-op and cannot refocus a prompt that
-- is being closed.
local function cancelTaskCaptureChooser()
	local chooser = taskCaptureChooser
	taskCaptureChooser = nil
	if chooser then
		pcall(function()
			chooser:delete()
		end)
	end
end

local function closeTaskCapturePrompt()
	cancelTaskCaptureTask()
	cancelTaskCaptureChooser()
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

local function trimCaptureText(rawText)
	local text = tostring(rawText or "")
	text = text:gsub("^%s+", "")
	text = text:gsub("%s+$", "")
	return text
end

local captureSuccessPrefix = "\226\156\147"
local captureFailurePrefix = "\226\154\160"
local captureLabelSeparator = " \194\183 "

local function truncateForBanner(rawText, maxLength)
	local text = trimCaptureText(rawText):gsub("%s+", " ")
	maxLength = maxLength or 100
	if text == "" or maxLength <= 0 then
		return text
	end

	local ellipsis = "..."
	local cutoffLength = math.max(maxLength - #ellipsis, 1)
	local utf8Module = utf8 or hs.utf8
	if type(utf8Module) == "table"
		and type(utf8Module.len) == "function"
		and type(utf8Module.offset) == "function"
	then
		local lenOk, textLength = pcall(utf8Module.len, text)
		if lenOk and type(textLength) == "number" then
			if textLength <= maxLength then
				return text
			end

			local offsetOk, cutoff = pcall(utf8Module.offset, text, cutoffLength + 1)
			if offsetOk and type(cutoff) == "number" then
				return trimCaptureText(text:sub(1, cutoff - 1)) .. ellipsis
			end
		end
	end

	if #text <= maxLength then
		return text
	end
	return trimCaptureText(text:sub(1, cutoffLength)) .. ellipsis
end

local function firstLineForBanner(rawText, maxLength)
	local text = trimCaptureText(rawText)
	text = text:gsub("\r\n", "\n"):gsub("\r", "\n")
	text = text:match("^[^\n]*") or text
	return truncateForBanner(text, maxLength or 140)
end

local function captureFailureDetail(decoded, stdOut, stdErr, fallback)
	if type(decoded) == "table"
		and type(decoded.error) == "string"
		and decoded.error ~= ""
	then
		return decoded.error
	end
	if stdErr ~= "" then
		return stdErr
	end
	if stdOut ~= "" then
		return stdOut
	end
	return fallback or "bob capture reported no detail"
end

local function captureKindLabel(kind)
	if kind == "area" then
		return "Area"
	end
	if kind == "project" then
		return "Project"
	end
	return ""
end

local function titleCaseWords(text)
	return (text:gsub("(%a)([%w_']*)", function(first, rest)
		return first:upper() .. rest
	end))
end

local function prettifyCaptureRouteLabel(rawLabel)
	local label = trimCaptureText(rawLabel)
	if label == "" then
		return ""
	end

	label = label:gsub("^.*/", "")
	label = label:gsub("%.md$", "")
	if label == "mac_inbox" then
		return "Inbox"
	end

	label = label:gsub("[_-]+", " ")
	return titleCaseWords(label)
end

local function captureDestinationLabel(decoded, pickedName, pickedKind)
	if type(decoded) ~= "table" or decoded.routed ~= true then
		return "Inbox"
	end

	local label = trimCaptureText(pickedName)
	local kindLabel = captureKindLabel(pickedKind)
	if label ~= "" and kindLabel ~= "" then
		label = label .. captureLabelSeparator .. kindLabel
	elseif label == "" then
		if type(decoded.route_label) == "string" then
			label = prettifyCaptureRouteLabel(decoded.route_label)
		end
		if label == "" and type(decoded.target) == "string" then
			label = prettifyCaptureRouteLabel(decoded.target)
		end
	end

	if label == "" then
		label = "Obsidian"
	end
	if decoded.placement == "created" and label ~= "Inbox" then
		return "New note" .. captureLabelSeparator .. label
	end
	return label
end

-- Lightweight breadcrumb logger for the capture notification path. Output lands
-- in the Hammerspoon console so a missing banner can be diagnosed as a creation
-- error, a send failure, or macOS declining to present a delivered notification.
local function captureNotifyDebug(fmt, ...)
	local ok, message = pcall(string.format, fmt, ...)
	if not ok then
		message = tostring(fmt)
	end
	hs.printf("%s", "[bob-capture-notify] " .. message)
end

-- Minimal percent-encoder used only when `hs.http.encodeForQuery` is missing, so
-- an unavailable helper can never abort notification delivery.
local function encodeForQueryFallback(text)
	return (tostring(text):gsub("[^%w%-_%.~]", function(char)
		return string.format("%%%02X", string.byte(char))
	end))
end

local function obsidianOpenUrl(targetPath)
	local path = trimCaptureText(targetPath)
	if path == "" then
		return nil
	end

	local encoded = nil
	if hs.http and type(hs.http.encodeForQuery) == "function" then
		local ok, result = pcall(hs.http.encodeForQuery, path)
		if ok and type(result) == "string" then
			encoded = result
		end
	end
	if not encoded then
		local ok, result = pcall(encodeForQueryFallback, path)
		if ok and type(result) == "string" then
			encoded = result
		end
	end
	if not encoded then
		return nil
	end

	return "obsidian://open?path=" .. encoded
end

local function obsidianContentImage()
	if not (hs.image and type(hs.image.imageFromAppBundle) == "function") then
		return nil
	end
	local ok, image = pcall(hs.image.imageFromAppBundle, "md.obsidian")
	if ok and type(image) == "userdata" then
		return image
	end
	return nil
end

-- After sending, log whether macOS actually presented the banner. A delivered
-- but unpresented notification (Focus mode, notification settings) is otherwise
-- indistinguishable from "nothing happened". Best-effort: never throws and never
-- shows a duplicate banner just because presented() is false.
local function scheduleCapturePresentationCheck(notification, label)
	if type(notification) ~= "userdata" then
		return
	end
	if not (hs.timer and type(hs.timer.doAfter) == "function") then
		return
	end

	hs.timer.doAfter(1.0, function()
		local function probe(method)
			if type(notification[method]) ~= "function" then
				return nil
			end
			local ok, value = pcall(notification[method], notification)
			if ok then
				return value
			end
			return nil
		end

		local delivered = probe("delivered")
		local presented = probe("presented")
		if presented == true then
			captureNotifyDebug("%s presented", label)
		elseif delivered == true then
			captureNotifyDebug(
				"%s delivered but not presented; check macOS Notification "
					.. "settings / Focus mode for Hammerspoon",
				label
			)
		else
			captureNotifyDebug(
				"%s not confirmed presented (delivered=%s presented=%s)",
				label,
				tostring(delivered),
				tostring(presented)
			)
		end
	end)
end

-- Deliver a notification, protecting every step so an optional attribute or a
-- single failing API call can never suppress the banner. Rich delivery is tried
-- first; any creation or send failure falls back to the proven
-- `hs.notify.show(...)` path using the same title, destination, and body.
local function notifyWithAttributes(attributes, callback, label)
	label = label or "notification"

	local title = attributes.title or "Notification"
	local subTitle = attributes.subTitle or ""
	local body = attributes.informativeText or ""

	local newOk, notification = pcall(hs.notify.new, callback, attributes)
	if newOk and type(notification) == "userdata" then
		local sendOk, sendErr = pcall(function()
			notification:send()
		end)
		if sendOk then
			captureNotifyDebug("%s sent (rich)", label)
			scheduleCapturePresentationCheck(notification, label)
			return
		end
		captureNotifyDebug("%s rich send failed: %s", label, tostring(sendErr))
	else
		captureNotifyDebug(
			"%s rich create failed: %s",
			label,
			tostring(notification)
		)
	end

	local showOk, showErr = pcall(hs.notify.show, title, subTitle, body)
	if showOk then
		captureNotifyDebug("%s sent (fallback)", label)
	else
		captureNotifyDebug("%s fallback failed: %s", label, tostring(showErr))
	end
end

local function notifyCaptureSuccess(decoded, pickedName, pickedKind)
	local title = captureSuccessPrefix .. " Captured"
	if decoded.kind == "task" then
		title = captureSuccessPrefix .. " Task captured"
	elseif decoded.kind == "bullet" then
		title = captureSuccessPrefix .. " Note captured"
	end

	-- Build the core banner from plain strings first so the optional
	-- enhancements below can only add to a guaranteed-deliverable notification.
	local attributes = { title = title }

	local subOk, subTitle =
		pcall(captureDestinationLabel, decoded, pickedName, pickedKind)
	if subOk and type(subTitle) == "string" then
		attributes.subTitle = subTitle
	end

	local bodyOk, body = pcall(truncateForBanner, decoded.text, 100)
	if bodyOk and type(body) == "string" and body ~= "" then
		attributes.informativeText = body
	end

	-- Obsidian icon: best-effort only.
	local image = obsidianContentImage()
	if image then
		attributes.contentImage = image
	end

	-- Click-to-open callback: best-effort only.
	local callback = nil
	local urlOk, openUrl = pcall(obsidianOpenUrl, decoded.target)
	if urlOk and type(openUrl) == "string" and openUrl ~= "" then
		callback = function()
			hs.urlevent.openURL(openUrl)
		end
	end

	notifyWithAttributes(attributes, callback, "capture-success")
end

local function notifyCaptureProblem(title, detail)
	local body = firstLineForBanner(detail, 140)
	if body == "" then
		body = "bob capture reported no detail"
	end

	notifyWithAttributes({
		title = captureFailurePrefix .. " " .. title,
		informativeText = body,
		soundName = hs.notify.defaultNotificationSound,
	}, nil, "capture-problem")
end

local function notifyCaptureFailure(detail)
	notifyCaptureProblem("Capture failed", detail)
end

-- A picker failure is surfaced explicitly instead of silently falling back to
-- the inbox, which would recreate the behavior this picker is meant to replace.
local function notifyTargetPickerFailure(detail)
	notifyCaptureProblem("Capture target picker failed", detail)
end

local function decodeCaptureJson(out)
	if out == "" then
		return nil
	end
	local decodeOk, decodeResult = pcall(hs.json.decode, out)
	if decodeOk then
		return decodeResult
	end
	return nil
end

-- Reuse the proven Bob Pomodoro launch pattern: a login shell with the GUI PATH
-- prepended and DATE=gdate exported when available.
local taskCaptureTargetsCommand = [[
PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH
exec bob capture-targets --format json
]]

-- The task text is passed as the positional parameter $1 and the optional forced
-- route as $2 (never interpolated) so arbitrary input cannot be evaluated by the
-- shell.
local taskCaptureCommand = [[
PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH
if [ -z "${DATE+x}" ] && command -v gdate >/dev/null 2>&1; then
	export DATE=gdate
fi
if [ -n "${2:-}" ]; then
	exec bob capture --format json --route "$2" -- "$1"
fi
exec bob capture --format json -- "$1"
]]

-- Run one staged `bob` invocation. The async callback is guarded by the live
-- task object so a late response cannot act on a prompt that has already moved
-- on or been dismissed. extraArgs become the positional parameters $1, $2, ...
local function startCaptureStage(command, extraArgs, onComplete, notifyFailure)
	if taskCaptureTask then
		return false
	end

	local args = { "-lc", command, "bob-capture" }
	for _, value in ipairs(extraArgs) do
		args[#args + 1] = value
	end

	local task
	task = hs.task.new("/bin/zsh", function(exitCode, stdOut, stdErr)
		if taskCaptureTask ~= task then
			return
		end
		taskCaptureTask = nil

		local out = trimCaptureText(stdOut)
		local err = trimCaptureText(stdErr)
		onComplete(exitCode, decodeCaptureJson(out), out, err)
	end, args)

	if not task then
		notifyFailure("could not create bob task")
		return false
	end

	taskCaptureTask = task
	local startOk, started = pcall(function()
		return task:start()
	end)
	if not startOk or not started then
		taskCaptureTask = nil
		if startOk then
			notifyFailure("could not start bob task")
		else
			notifyFailure(started)
		end
		return false
	end

	return true
end

-- Write the task. A nil/empty route runs the unrouted inbox path; a non-empty
-- route forces `--route`. On success the prompt is closed; on failure the prompt
-- stays open so the typed text is not lost.
local function runFinalCapture(text, route, pickedName, pickedKind)
	local extraArgs = { text }
	if type(route) == "string" and route ~= "" then
		extraArgs[#extraArgs + 1] = route
	end

	startCaptureStage(taskCaptureCommand, extraArgs, function(exitCode, decoded, out, err)
		if exitCode == 0
			and type(decoded) == "table"
			and decoded.ok == true
		then
			-- Notification delivery must never block closing the prompt. If the
			-- success handler throws before it reaches its own fallback, show a
			-- minimal banner and still close the prompt.
			local notifyOk, notifyErr =
				pcall(notifyCaptureSuccess, decoded, pickedName, pickedKind)
			if not notifyOk then
				captureNotifyDebug(
					"capture-success handler error: %s",
					tostring(notifyErr)
				)
				pcall(
					hs.notify.show,
					captureSuccessPrefix .. " Captured",
					"",
					""
				)
			end
			closeTaskCapturePrompt()
			return
		end

		notifyCaptureFailure(captureFailureDetail(decoded, out, err))
	end, notifyCaptureFailure)
end

-- Derive the picker subtext that distinguishes inbox, area, and project rows.
-- This textual distinction is the source of truth even when a per-kind image is
-- unavailable.
local function captureTargetSubText(target)
	if target.is_default == true or target.kind == "inbox" then
		return "Inbox - default"
	end
	if target.kind == "area" then
		return "Area"
	end
	if target.kind == "project" then
		local status = target.status
		if type(status) == "string" and status ~= "" then
			return "Project - " .. status
		end
		return "Project"
	end
	return ""
end

-- Best-effort per-kind row image. A missing named image simply yields no image,
-- leaving the subtext to carry the distinction.
local function captureTargetImage(kind)
	local names = {
		inbox = "NSInbox",
		area = "NSFolder",
		project = "NSListViewTemplate",
	}
	local imageName = names[kind]
	if not imageName then
		return nil
	end
	local ok, image = pcall(hs.image.imageFromName, imageName)
	if ok then
		return image
	end
	return nil
end

-- Map the CLI target contract onto chooser rows, keeping only area and project
-- targets. Inbox/default rows are dropped because plain Enter already captures to
-- the inbox; the picker exists purely to choose an area or project. The emitted
-- CLI order is otherwise preserved.
local function buildCaptureChoices(targets)
	local choices = {}
	for _, target in ipairs(targets) do
		if type(target) == "table"
			and type(target.route) == "string"
			and (target.kind == "area" or target.kind == "project")
		then
			local choice = {
				text = tostring(target.name or target.route),
				subText = captureTargetSubText(target),
				route = target.route,
				kind = target.kind,
			}
			local image = captureTargetImage(target.kind)
			if image then
				choice.image = image
			end
			choices[#choices + 1] = choice
		end
	end
	return choices
end

-- Show the native area/project picker for a trailing `@` or `@#section` request.
-- Dismissing it refocuses the prompt with the typed text intact. For a bare `@`,
-- selecting any row forces that row's route, since the inbox is reachable only
-- via plain Enter. For an `@#section` request, the chosen route is synthesized
-- into a concrete leading `@route#section` token so Bob's own parser owns the
-- bullet placement; leading the token makes the picked route win even when the
-- body itself begins with an explicit `@route`.
local function showTaskCaptureChooser(text, targets, bulletSuffix)
	local choices = buildCaptureChoices(targets)
	if #choices == 0 then
		notifyTargetPickerFailure("no capture targets were returned")
		return
	end

	local chooser
	chooser = hs.chooser.new(function(choice)
		if taskCaptureChooser ~= chooser then
			return
		end
		taskCaptureChooser = nil

		if type(choice) ~= "table" or type(choice.route) ~= "string" then
			focusTaskCapturePrompt()
			return
		end

		if bulletSuffix then
			runFinalCapture(
				"@" .. choice.route .. bulletSuffix .. " " .. text,
				nil,
				choice.text,
				choice.kind
			)
		else
			runFinalCapture(text, choice.route, choice.text, choice.kind)
		end
	end)

	if not chooser then
		notifyTargetPickerFailure("could not create the target picker")
		return
	end

	taskCaptureChooser = chooser
	chooser:placeholderText("Capture target")
	chooser:choices(choices)
	chooser:show()
end

-- Fetch the picker rows. A failure here surfaces a dedicated picker notification
-- instead of silently falling back to the inbox. The optional bullet suffix is
-- threaded through to the chooser so an `@#section` request can be finalized as a
-- routed bullet once a target is picked.
local function startTargetsStage(text, bulletSuffix)
	startCaptureStage(taskCaptureTargetsCommand, {}, function(exitCode, decoded, out, err)
		if exitCode == 0
			and type(decoded) == "table"
			and decoded.ok == true
			and type(decoded.targets) == "table"
		then
			showTaskCaptureChooser(text, decoded.targets, bulletSuffix)
			return
		end

		notifyTargetPickerFailure(captureFailureDetail(
			decoded,
			out,
			err,
			"bob capture-targets reported no detail"
		))
	end, notifyTargetPickerFailure)
end

-- Detect the area/project picker marker as the final whitespace-separated token,
-- preceded by whitespace, e.g. `foo bar baz @`. Two forms are recognized:
--
--   * `@`            -> open the picker and capture a normal task.
--   * `@#<prefix>`   -> open the picker and capture a bullet routed to the chosen
--                       note's matching section; a bare `@#` uses the first
--                       non-`Tasks` section, mirroring Bob's concrete `@note#`.
--
-- The marker is opt-in UI sugar handled entirely on the Hammerspoon side, so
-- `foo@`, `foo @cash`, `foo @cash#Ideas`, `@cash foo`, `foo @ #Ideas`, and
-- `foo @#Ideas extra` are left untouched and Bob's own route parser keeps owning
-- explicit @route input. The `#<prefix>` case is preserved exactly because Bob
-- preserves the prefix and compares headings case-insensitively.
--
-- Returns the task text to capture, whether the picker was requested, and an
-- optional bullet route suffix (`#Ideas` or `#`) for the `@#...` form.
local function parseCaptureRequest(rawText)
	local text = trimCaptureText(rawText)

	local strippedBullet, bulletPrefix = text:match("^(.-)%s+@#(%S*)$")
	if strippedBullet then
		return trimCaptureText(strippedBullet), true, "#" .. bulletPrefix
	end

	local stripped = text:match("^(.-)%s+@$")
	if stripped then
		return trimCaptureText(stripped), true, nil
	end

	return text, false, nil
end

-- Snapshot the prompt text and route it. A trailing `@` or `@#section` marker
-- opts into the area/project picker with the marker stripped; everything else
-- captures immediately, letting `bob capture` own route parsing and the inbox
-- default. An empty body after stripping the marker is a no-op.
local function submitCapturedTask(rawText)
	if taskCaptureTask or taskCaptureChooser then
		return
	end

	local text, pickerRequested, bulletSuffix = parseCaptureRequest(rawText)
	if text == "" then
		return
	end

	if pickerRequested then
		startTargetsStage(text, bulletSuffix)
		return
	end

	runFinalCapture(text, nil)
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

		if payload.action == "submit" then
			submitCapturedTask(payload.text)
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
			cancelTaskCaptureTask()
			cancelTaskCaptureChooser()
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
