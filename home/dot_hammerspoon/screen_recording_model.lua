-- Pure state and presentation model for the region screen recorder.
-- This module intentionally has no Hammerspoon dependencies or side effects.
local M = {}

M.CHORD = { mods = { "ctrl", "alt", "shift" }, key = "v" }
M.CHORD_LABEL = "⌃⌥⇧V"
M.ACCENT = "#E3413B"
M.WARN = "#FF9F0A"
M.OK = "#30d158"
M.CAP_SECONDS = 600
M.WARN_AT = 540
M.DEBOUNCE = 0.15
M.CHROME_GAP = 4
M.SETTINGS_KEY = "macrecLastRegion"
M.FALLBACK_SETTINGS_KEY = "macscrotLastRegion"
M.PILL_WIDTH = 190
M.PILL_HEIGHT = 30
M.BRACKET_LENGTH = 20
M.BRACKET_THICKNESS = 3

M.STATES = {
	idle = "idle",
	selecting = "selecting",
	starting = "starting",
	recording = "recording",
	stopping = "stopping",
	shipping = "shipping",
	done = "done",
	failed = "failed",
}

local TERMINAL_SESSION_STATES = {
	done = true,
	failed = true,
	discarded = true,
}

local function is_number(value)
	return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function copy_table(value)
	local result = {}
	if type(value) == "table" then
		for key, item in pairs(value) do
			result[key] = item
		end
	end
	return result
end

local function copy_model(model)
	local result = copy_table(model)
	result.session = copy_table(model and model.session)
	result.notifiedSessions = copy_table(model and model.notifiedSessions)
	result.clipboardBaselines = copy_table(model and model.clipboardBaselines)
	return result
end

local function effect(effects, kind, fields)
	local item = copy_table(fields)
	item.type = kind
	table.insert(effects, item)
end

local function event_type(event)
	if type(event) ~= "table" then
		return nil
	end
	return event.type or event.event
end

local function event_session_id(event)
	local session_id = event.session_id or event.id
	if session_id ~= nil then
		return session_id
	end
	if type(event.session) == "table" then
		return event.session.id
	end
	return nil
end

local function is_stale(model, event)
	local current_id = model.session and model.session.id
	local incoming_id = event_session_id(event)
	return current_id ~= nil and incoming_id ~= nil and incoming_id ~= current_id
end

local function stop_recording(model, effects, reason, event)
	model.state = M.STATES.stopping
	model.stopReason = reason
	if is_number(event and event.change_count) then
		model.clipboardBaseline = event.change_count
		model.clipboardBaselines = model.clipboardBaselines or {}
		if model.session and model.session.id then
			model.clipboardBaselines[model.session.id] = event.change_count
		end
	end
	effect(effects, "hide_chrome")
	if reason == "chord" or reason == "menu" then
		effect(effects, "flash_shutter")
	end
	effect(effects, "stop_recorder", {
		reason = reason,
		session_id = model.session and model.session.id,
	})
	effect(effects, "update_menu")
end

local function elapsed_for(model, now)
	local started_at = model.session and model.session.started_at
	if not is_number(started_at) or not is_number(now) then
		return 0
	end
	return math.max(0, now - started_at)
end

local function notify_terminal_session(model, effects, session, event)
	local acked = type(session.acked) == "table" and session.acked.notified == true
	model.notifiedSessions = model.notifiedSessions or {}
	if acked or M.isDismissed(session) or model.notifiedSessions[session.id] then
		return
	end
	local recovered = session.recovered == true
	local notification_context = copy_table(event and event.context)
	notification_context.recovered = recovered
	local baseline = model.clipboardBaselines and model.clipboardBaselines[session.id]
	if baseline == nil and model.session and model.session.id == session.id then
		baseline = model.clipboardBaseline
	end
	local copied = M.clipboardDecision(baseline, event and event.clipboard_change_count, recovered)
	notification_context.copied = copied
	if copied and type(session.mp4) == "string" then
		effect(effects, "copy_path", { path = session.mp4, session_id = session.id })
	end
	effect(effects, "notify", {
		notification = M.notification(session, notification_context),
		session_id = session.id,
	})
	effect(effects, "ack", { session_id = session.id, kind = "notified" })
	model.notifiedSessions[session.id] = true
end

local function apply_terminal_session(model, effects, session, event)
	model.session = copy_table(session)
	if session.status == "discarded" then
		model.state = M.STATES.idle
		model.discardPending = false
		effect(effects, "hide_chrome")
		effect(effects, "update_menu")
		return
	end

	local is_failed = session.status == "failed"
	model.state = is_failed and M.STATES.failed or M.STATES.done
	effect(effects, "hide_chrome")
	notify_terminal_session(model, effects, session, event)
	effect(effects, "update_menu")
end

local function valid_region(region)
	return type(region) == "table"
		and is_number(region.x)
		and is_number(region.y)
		and is_number(region.w)
		and is_number(region.h)
		and region.w > 0
		and region.h > 0
end

local function valid_rect(rect)
	return valid_region(rect)
end

local function session_state_from_status(active)
	if active.state == "starting" then
		return M.STATES.starting
	elseif active.state == "recording" then
		return M.STATES.recording
	elseif active.state == "stopping" then
		return M.STATES.stopping
	end
	return M.STATES.idle
end

local function refresh_from_status(model, effects, event)
	local status = event.status
	if type(status) ~= "table" then
		status = M.parseStatus(status)
	end
	if status.state == "idle" and status.reason then
		model.state = M.STATES.idle
		model.session = {}
		model.reason = status.reason
		effect(effects, "hide_chrome")
		effect(effects, "update_menu")
		return
	end
	status = M.userStatus(status)
	for _, session in ipairs(status.sessions or {}) do
		if TERMINAL_SESSION_STATES[session.status] and session.status ~= "discarded" then
			notify_terminal_session(model, effects, session, event)
		end
	end
	model.reason = nil
	if type(status.active) == "table" then
		model.session = copy_table(status.active)
		model.state = session_state_from_status(status.active)
		if model.state == M.STATES.recording then
			effect(effects, "show_chrome", { session = copy_table(model.session) })
		else
			effect(effects, "hide_chrome")
		end
		effect(effects, "update_menu")
		return
	end

	local prior_id = model.session and model.session.id
	local found
	for _, session in ipairs(status.sessions or {}) do
		if prior_id ~= nil and session.id == prior_id then
			found = session
			break
		end
	end
	if not found then
		for _, session in ipairs(status.sessions or {}) do
			if session.orphaned == true then
				found = session
				break
			end
		end
	end
	if found and found.orphaned == true and not found.recovered then
		model.session = copy_table(found)
		model.state = M.STATES.shipping
		if model.recoverRequestedId ~= found.id then
			effect(effects, "recover", { session_id = found.id })
			model.recoverRequestedId = found.id
		end
		effect(effects, "hide_chrome")
		effect(effects, "update_menu")
		return
	end
	if found and TERMINAL_SESSION_STATES[found.status] then
		if found.status == "discarded" or M.isDismissed(found) then
			model.state = M.STATES.idle
			model.session = copy_table(found)
			model.discardPending = false
			effect(effects, "hide_chrome")
			effect(effects, "update_menu")
		else
			apply_terminal_session(model, effects, found, event)
		end
		return
	end
	if found and (found.status == "finalizing" or found.status == "encoding" or found.status == "uploading") then
		model.session = copy_table(found)
		model.state = M.STATES.shipping
		effect(effects, "hide_chrome")
		effect(effects, "update_menu")
		return
	end

	model.state = M.STATES.idle
	model.session = {}
	effect(effects, "hide_chrome")
	effect(effects, "update_menu")
end

-- Reduce one event into a new model and an ordered list of side-effect requests.
-- Events are tables with a `type` plus event-specific fields. The input model is
-- never mutated, so callers can retain it for debugging or tests.
function M.reduce(previous, event, now)
	local model = copy_model(previous)
	local effects = {}
	local kind = event_type(event)
	event = type(event) == "table" and event or {}
	now = is_number(now) and now or 0
	model.state = model.state or M.STATES.idle
	model.session = model.session or {}

	if is_stale(model, event) then
		return model, effects
	end

	if kind == "chord" then
		if event["repeat"] == true then
			return model, effects
		end
		if is_number(model.lastChordAt) and now - model.lastChordAt < M.DEBOUNCE then
			return model, effects
		end
		model.lastChordAt = now
		if model.state == M.STATES.idle or model.state == M.STATES.done or model.state == M.STATES.failed then
			model.state = M.STATES.selecting
			model.session = {}
			effect(effects, "open_selector", {
				settings_key = M.SETTINGS_KEY,
				fallback_settings_key = M.FALLBACK_SETTINGS_KEY,
			})
			effect(effects, "update_menu")
		elseif model.state == M.STATES.selecting then
			model.state = M.STATES.idle
			effect(effects, "close_selector")
			effect(effects, "update_menu")
		elseif model.state == M.STATES.starting then
			model.discardPending = true
			model.cancelPending = true
		elseif model.state == M.STATES.recording then
			stop_recording(model, effects, "chord", event)
		elseif model.state == M.STATES.stopping then
			return model, effects
		elseif model.state == M.STATES.shipping then
			model.state = M.STATES.selecting
			effect(effects, "open_selector", {
				settings_key = M.SETTINGS_KEY,
				fallback_settings_key = M.FALLBACK_SETTINGS_KEY,
			})
		end
	elseif kind == "enter" then
		if model.state ~= M.STATES.selecting then
			return model, effects
		end
		if not valid_region(event.region) then
			model.state = M.STATES.idle
			effect(effects, "close_selector")
			effect(effects, "notify", {
				notification = { title = "Recording didn't start", body = "The selected region is invalid." },
			})
			effect(effects, "update_menu")
			return model, effects
		end
		model.state = M.STATES.starting
		model.clipboardBaseline = nil
		model.selection = { region = copy_table(event.region), mic = event.mic == true }
		model.cancelPending = false
		model.discardPending = false
		effect(effects, "close_selector")
		effect(effects, "start_recorder", {
			region = copy_table(event.region),
			mic = event.mic == true,
			save_default = event.save_default == true or event.command_enter == true,
			max_seconds = M.CAP_SECONDS,
		})
		effect(effects, "update_menu")
	elseif kind == "picker_cancel" or kind == "cancel" then
		if model.state == M.STATES.selecting then
			model.state = M.STATES.idle
			effect(effects, "close_selector")
			effect(effects, "update_menu")
		end
	elseif kind == "start_ok" then
		if model.state ~= M.STATES.starting then
			return model, effects
		end
		local session = copy_table(event.session)
		if not session.id then
			session.id = event.id
		end
		local selection = model.selection or {}
		session.region = session.region or copy_table(selection.region)
		session.mic = session.mic == nil and selection.mic == true or session.mic == true
		session.started_at = session.started_at or now
		model.session = session
		model.selection = nil
		if model.discardPending or model.cancelPending then
			model.state = M.STATES.stopping
			model.discardPending = true
			model.cancelPending = false
			effect(effects, "discard", { session_id = session.id })
			effect(effects, "hide_chrome")
			effect(effects, "update_menu")
		else
			model.state = M.STATES.recording
			effect(effects, "show_chrome", { session = copy_table(session) })
			effect(effects, "update_menu")
		end
	elseif kind == "start_fail" then
		if model.state ~= M.STATES.starting then
			return model, effects
		end
		model.state = M.STATES.idle
		model.session = {}
		model.selection = nil
		model.discardPending = false
		model.cancelPending = false
		effect(effects, "notify", {
			notification = {
				title = "Recording didn't start",
				body = tostring(event.reason or "The recorder failed to start."),
			},
		})
		effect(effects, "update_menu")
	elseif kind == "sleep" or kind == "lock" or kind == "display_loss" or kind == "stop" then
		if model.state == M.STATES.recording then
			local reason = kind == "display_loss" and "display" or kind
			if kind == "stop" then
				reason = event.reason or "menu"
			end
			stop_recording(model, effects, reason, event)
		end
	elseif kind == "discard_confirmed" then
		if model.state == M.STATES.recording then
			model.state = M.STATES.stopping
			model.stopReason = "discard"
			model.discardPending = true
			if is_number(event.change_count) then
				model.clipboardBaseline = event.change_count
			end
			effect(effects, "hide_chrome")
			effect(effects, "flash_shutter")
			effect(effects, "discard", { session_id = model.session.id })
			effect(effects, "update_menu")
		end
	elseif kind == "recorder_gone" or kind == "stop_done" then
		if is_number(event.change_count) and model.clipboardBaseline == nil then
			model.clipboardBaseline = event.change_count
			model.clipboardBaselines = model.clipboardBaselines or {}
			if model.session and model.session.id then
				model.clipboardBaselines[model.session.id] = event.change_count
			end
		end
		if model.state == M.STATES.stopping then
			model.state = model.discardPending and M.STATES.idle or M.STATES.shipping
			model.discardPending = false
			effect(effects, "hide_chrome")
			effect(effects, "update_menu")
		elseif model.state == M.STATES.recording then
			model.state = M.STATES.shipping
			model.stopReason = event.reason or model.stopReason or "system"
			effect(effects, "hide_chrome")
			effect(effects, "update_menu")
		end
	elseif kind == "status_refresh" then
		refresh_from_status(model, effects, event)
	elseif kind == "tick" then
		if model.state == M.STATES.recording then
			if elapsed_for(model, now) >= M.CAP_SECONDS then
				stop_recording(model, effects, "cap", event)
			else
				effect(effects, "update_menu", { elapsed = elapsed_for(model, now) })
			end
		end
	end
	return model, effects
end

function M.chromeLayout(region, screenFrame)
	local layout = { strips = {}, brackets = {}, pill = { placement = "hidden" }, pillPlacement = "hidden" }
	if not valid_region(region) or not valid_rect(screenFrame) then
		layout.reason = "invalid region or screen frame"
		return layout
	end

	local gap = M.CHROME_GAP
	local line = 1.5
	local left = region.x
	local top = region.y
	local right = region.x + region.w
	local bottom = region.y + region.h
	local outerLeft = left - gap - line
	local outerTop = top - gap - line
	local outerRight = right + gap
	local outerBottom = bottom + gap
	local outerWidth = region.w + (2 * gap) + (2 * line)
	layout.strips = {
		top = { x = outerLeft, y = outerTop, w = outerWidth, h = line },
		bottom = { x = outerLeft, y = outerBottom, w = outerWidth, h = line },
		left = { x = left - gap - line, y = top, w = line, h = region.h },
		right = { x = right + gap, y = top, w = line, h = region.h },
	}

	local length = M.BRACKET_LENGTH
	local thickness = M.BRACKET_THICKNESS
	local bracketLeft = left - gap - thickness
	local bracketRight = right + gap
	local bracketTop = top - gap - thickness
	local bracketBottom = bottom + gap
	layout.brackets = {
		{
			corner = "top_left",
			axis = "horizontal",
			x = left - gap - length,
			y = bracketTop,
			w = length,
			h = thickness,
		},
		{ corner = "top_left", axis = "vertical", x = bracketLeft, y = top - gap - length, w = thickness, h = length },
		{ corner = "top_right", axis = "horizontal", x = right + gap, y = bracketTop, w = length, h = thickness },
		{
			corner = "top_right",
			axis = "vertical",
			x = bracketRight,
			y = top - gap - length,
			w = thickness,
			h = length,
		},
		{
			corner = "bottom_left",
			axis = "horizontal",
			x = left - gap - length,
			y = bracketBottom,
			w = length,
			h = thickness,
		},
		{ corner = "bottom_left", axis = "vertical", x = bracketLeft, y = bottom + gap, w = thickness, h = length },
		{ corner = "bottom_right", axis = "horizontal", x = right + gap, y = bracketBottom, w = length, h = thickness },
		{ corner = "bottom_right", axis = "vertical", x = bracketRight, y = bottom + gap, w = thickness, h = length },
	}

	local screenLeft = screenFrame.x
	local screenTop = screenFrame.y
	local screenRight = screenFrame.x + screenFrame.w
	local screenBottom = screenFrame.y + screenFrame.h
	local fullScreen = left <= screenLeft + 0.001
		and top <= screenTop + 0.001
		and right >= screenRight - 0.001
		and bottom >= screenBottom - 0.001
	if fullScreen then
		return layout
	end

	local pillWidth = M.PILL_WIDTH
	local pillHeight = M.PILL_HEIGHT
	local candidates = {
		{
			placement = "bottom_right",
			frame = { x = right - pillWidth, y = bottom + gap, w = pillWidth, h = pillHeight },
		},
		{
			placement = "top_right",
			frame = { x = right - pillWidth, y = top - gap - pillHeight, w = pillWidth, h = pillHeight },
		},
		{
			placement = "right",
			frame = { x = right + gap, y = bottom - pillHeight, w = pillWidth, h = pillHeight },
		},
	}
	for _, candidate in ipairs(candidates) do
		local frame = candidate.frame
		if
			frame.x >= screenLeft
			and frame.y >= screenTop
			and frame.x + frame.w <= screenRight
			and frame.y + frame.h <= screenBottom
		then
			layout.pill = { placement = candidate.placement, frame = frame }
			layout.pillPlacement = candidate.placement
			break
		end
	end
	return layout
end

function M.formatElapsed(seconds)
	local elapsed = is_number(seconds) and math.max(0, math.floor(seconds)) or 0
	return string.format("%d:%02d", math.floor(elapsed / 60), elapsed % 60)
end

function M.timerTone(seconds)
	return is_number(seconds) and seconds >= M.WARN_AT and "warn" or "accent"
end

local function state_and_session(value)
	if type(value) == "string" then
		return value, {}
	end
	value = type(value) == "table" and value or {}
	return value.state or "idle", value.session or value
end

local function elapsed_for_session(session, now)
	if is_number(session.elapsed) then
		return session.elapsed
	end
	if is_number(session.started_at) and is_number(now) then
		return math.max(0, now - session.started_at)
	end
	return 0
end

function M.menuTitle(value, now)
	local state, session = state_and_session(value)
	local elapsed = elapsed_for_session(session, now)
	local text = ""
	local role = "label"
	if state == M.STATES.recording then
		if elapsed >= M.WARN_AT then
			text = "● "
				.. M.formatElapsed(elapsed)
				.. " · "
				.. M.formatElapsed(math.max(0, M.CAP_SECONDS - elapsed))
				.. " left"
		else
			text = "● " .. M.formatElapsed(elapsed)
		end
		if session.mic == true then
			text = text .. " · MIC"
		end
		role = M.timerTone(elapsed)
	elseif state == M.STATES.starting then
		text, role = "● Starting", "accent"
	elseif state == M.STATES.stopping or state == M.STATES.shipping then
		local count = type(value) == "table" and value.shipping_count or session.shipping_count or 1
		text = "⇡" .. (count > 1 and tostring(count) or "")
		role = "shipping"
	elseif state == M.STATES.done then
		text, role = "✓", "ok"
	elseif state == M.STATES.failed then
		text, role = "⚠ rec", "warn"
	end
	if text == "" then
		return {}
	end
	return { { text = text, role = role } }
end

local function row(kind, text, role, action, enabled)
	local segments = {}
	if text ~= nil and text ~= "" then
		segments[1] = { text = text, role = role or kind }
	end
	local result = { kind = kind, segments = segments }
	if action then
		result.action = action
	end
	if enabled ~= nil then
		result.enabled = enabled
	end
	return result
end

function M.menuItems(value, now)
	local state, session = state_and_session(value)
	local elapsed = elapsed_for_session(session, now)
	if state == M.STATES.recording then
		local region = session.region or {}
		local size = is_number(region.w)
				and is_number(region.h)
				and string.format("%.0f × %.0f pt", region.w, region.h)
			or "Region"
		local display = session.display_name or session.display or "Display"
		local mic = session.mic == true and "Mic on" or "Mic off"
		return {
			row("header", "● Recording · " .. M.formatElapsed(elapsed), "accent", nil, false),
			row("info", size .. " · " .. display .. " · " .. mic, "info", nil, false),
			row("action", "Stop & Upload  " .. M.CHORD_LABEL, "action", "stop_upload", true),
			row("action", "Discard Recording…", "action", "discard", true),
		}
	elseif state == M.STATES.selecting then
		return {
			row("header", "● Select recording region", "accent", nil, false),
			row("action", "Cancel", "action", "cancel", true),
		}
	elseif state == M.STATES.starting then
		return { row("header", "● Starting recording…", "accent", nil, false) }
	elseif state == M.STATES.stopping or state == M.STATES.shipping then
		return { row("header", "⇡ Uploading recording…", "shipping", nil, false) }
	elseif state == M.STATES.failed then
		return {
			row("header", "⚠ Recording not uploaded", "warn", nil, false),
			row("action", "Retry", "action", "retry", true),
			row("action", "Reveal", "action", "reveal", true),
			row("action", "Show Log", "action", "show_log", true),
			row("action", "Dismiss", "action", "dismiss", true),
		}
	elseif state == M.STATES.done then
		return { row("header", "✓ Recording uploaded", "ok", nil, false) }
	end
	return {}
end

function M.selectorBadge(state)
	state = type(state) == "table" and state or {}
	local region = state.region or (state.selection and state.selection.region) or {}
	local size = is_number(region.w) and is_number(region.h) and string.format("%.0f × %.0f", region.w, region.h)
		or "Select region"
	local mic = state.mic == true or (state.selection and state.selection.mic == true)
	return "● REC" .. (mic and " · MIC" or "") .. " · " .. size
end

function M.selectorHint(state)
	state = type(state) == "table" and state or {}
	local mic = state.mic == true or (state.selection and state.selection.mic == true)
	return "Drag: new box · ⌘-drag: move · Corners: resize · F: full screen · W: window\n⏎: record · ⌘⏎: record + save default · M: mic "
		.. (mic and "on" or "off")
		.. " · Esc or "
		.. M.CHORD_LABEL
		.. ": cancel"
end

local function host_name(host)
	if host == "apollo" then
		return "Apollo"
	elseif host == "athena" then
		return "Athena"
	end
	return tostring(host)
end

function M.hostsLabel(hosts, details)
	hosts = type(hosts) == "table" and hosts or {}
	details = type(details) == "table" and details or {}
	local successful = {}
	local other = {}
	for _, name in ipairs({ "apollo", "athena" }) do
		local status = hosts[name]
		if status == "ok" then
			table.insert(successful, host_name(name))
		elseif status == "failed" or status == "skipped" then
			local suffix = status
			if status == "skipped" and type(details[name]) == "string" and details[name] ~= "" then
				suffix = suffix .. " (" .. details[name] .. ")"
			end
			table.insert(other, name .. " " .. suffix)
		end
	end
	local label
	if #successful == 2 then
		label = successful[1] .. " + " .. successful[2]
	elseif #successful == 1 then
		label = successful[1]
	elseif #other > 0 then
		label = table.concat(other, " · ")
	else
		label = "No hosts"
	end
	if #successful > 0 and #other > 0 then
		label = label .. " · " .. table.concat(other, " · ")
	end
	return label
end

function M.formatBytes(bytes)
	if not is_number(bytes) or bytes < 0 then
		return "0 B"
	end
	if bytes < 1000 then
		return string.format("%d B", math.floor(bytes))
	elseif bytes < 1000000 then
		return string.format("%.1f kB", bytes / 1000)
	elseif bytes < 1000000000 then
		return string.format("%.1f MB", bytes / 1000000)
	end
	return string.format("%.1f GB", bytes / 1000000000)
end

function M.clipboardDecision(baselineChangeCount, nowChangeCount, recovered)
	return recovered ~= true
		and is_number(baselineChangeCount)
		and is_number(nowChangeCount)
		and baselineChangeCount == nowChangeCount
end

local function notification_path(session)
	return session.mp4 or session.path or session.name or "the saved recording"
end

function M.notification(session, context)
	session = type(session) == "table" and session or {}
	context = type(context) == "table" and context or {}
	local recovered = context.recovered == true or session.recovered == true
	local failed = session.status == "failed" or context.failed == true
	local hosts = M.hostsLabel(session.hosts, session.host_detail)
	local details =
		table.concat({ M.formatElapsed(session.duration_s or 0), M.formatBytes(session.bytes or 0), hosts }, " · ")
	local has_failed = false
	local has_skipped = false
	for _, status in pairs(session.hosts or {}) do
		has_failed = has_failed or status == "failed"
		has_skipped = has_skipped or status == "skipped"
	end
	local kind = failed and "failed" or has_failed and "partial" or has_skipped and "skipped" or "done"
	local title = failed and "Recording not uploaded" or "Recording uploaded"
	if recovered and not failed then
		title = "Recovered recording uploaded"
	end
	local path = notification_path(session)
	local copied = context.copied == true
	local body
	if failed then
		body = "Saved locally: " .. path .. " · Retry from the menu bar"
	else
		if session.stop_reason == "cap" then
			details = "Stopped at " .. M.formatElapsed(session.duration_s or M.CAP_SECONDS) .. " cap · " .. details
		end
		body = path .. (copied and " · path copied" or "")
	end
	return {
		kind = kind,
		title = title,
		subtitle = details,
		body = body,
		path = path,
		action = copied and "Reveal" or "Copy path",
		poster = session.poster,
	}
end

local function valid_ack(acked)
	if acked == nil then
		return true
	end
	if type(acked) ~= "table" then
		return false
	end
	for _, key in ipairs({ "notified", "adopted", "dismissed" }) do
		if acked[key] ~= nil and type(acked[key]) ~= "boolean" then
			return false
		end
	end
	return true
end

local function validate_active(active)
	if type(active) ~= "table" then
		return false
	end
	if type(active.id) ~= "string" or active.id == "" then
		return false
	end
	if active.state ~= "starting" and active.state ~= "recording" and active.state ~= "stopping" then
		return false
	end
	if not valid_region(active.region) then
		return false
	end
	if type(active.mic) ~= "boolean" or type(active.probe) ~= "boolean" then
		return false
	end
	if not is_number(active.started_at) or not is_number(active.cap_seconds) or active.cap_seconds <= 0 then
		return false
	end
	if type(active.recorder_alive) ~= "boolean" then
		return false
	end
	if type(active.name) ~= "string" then
		return false
	end
	return true
end

local function validate_session(session)
	if type(session) ~= "table" then
		return false
	end
	if type(session.id) ~= "string" or session.id == "" or type(session.name) ~= "string" then
		return false
	end
	local allowed = {
		recording = true,
		finalizing = true,
		encoding = true,
		uploading = true,
		done = true,
		failed = true,
		discarded = true,
	}
	if not allowed[session.status] then
		return false
	end
	if session.schema ~= 1 then
		return false
	end
	-- macrec_ship imports have no screen coordinates, including while encoding.
	-- Accept their exact sentinel without allowing empty live capture regions.
	local region = session.region
	local regionless_import = session.stop_reason == "import"
		and type(region) == "table"
		and region.x == 0
		and region.y == 0
		and region.w == 0
		and region.h == 0
	if
		(not valid_region(region) and not regionless_import)
		or type(session.mic) ~= "boolean"
		or type(session.probe) ~= "boolean"
	then
		return false
	end
	if not is_number(session.started_at) or not is_number(session.cap_seconds) or session.cap_seconds <= 0 then
		return false
	end
	if
		type(session.orphaned) ~= "boolean"
		or type(session.log) ~= "string"
		or type(session.acked) ~= "table"
		or not valid_ack(session.acked)
	then
		return false
	end
	if session.duration_s ~= nil and (not is_number(session.duration_s) or session.duration_s < 0) then
		return false
	end
	if session.bytes ~= nil and (not is_number(session.bytes) or session.bytes < 0) then
		return false
	end
	if session.hosts ~= nil then
		if type(session.hosts) ~= "table" then
			return false
		end
		for host, value in pairs(session.hosts) do
			if host ~= "apollo" and host ~= "athena" then
				return false
			end
			if value ~= "ok" and value ~= "failed" and value ~= "skipped" and value ~= "pending" then
				return false
			end
		end
	end
	if session.host_detail ~= nil and type(session.host_detail) ~= "table" then
		return false
	end
	if session.host_detail ~= nil then
		for host, detail in pairs(session.host_detail) do
			if (host ~= "apollo" and host ~= "athena") or type(detail) ~= "string" then
				return false
			end
		end
	end
	return true
end

local function is_null_sentinel(value)
	return type(value) == "userdata" and tostring(value):lower():find("null", 1, true) ~= nil
end

-- True once the user dismissed a session's failure (`macrec ack ID dismissed`).
function M.isDismissed(session)
	return type(session) == "table" and type(session.acked) == "table" and session.acked.dismissed == true
end

-- The user-facing view of a parsed status. Doctor probes run through macrec but
-- are self-tests, not recordings: they never draw chrome, update the menu bar,
-- notify, or surface as failed or orphaned sessions.
function M.userStatus(status)
	if type(status) ~= "table" then
		return status
	end
	local view = {}
	for key, value in pairs(status) do
		view[key] = value
	end
	if type(status.active) == "table" and status.active.probe == true then
		view.active = nil
		view.state = M.STATES.idle
	end
	local sessions = {}
	for _, session in ipairs(status.sessions or {}) do
		if not (type(session) == "table" and session.probe == true) then
			table.insert(sessions, session)
		end
	end
	view.sessions = sessions
	return view
end

-- Validate `macrec status --json` schema 1. Invalid or absent data always
-- returns an idle-shaped result with a human-readable reason.
function M.parseStatus(decoded)
	local function invalid(reason)
		return { state = M.STATES.idle, active = nil, sessions = {}, reason = reason }
	end
	if type(decoded) ~= "table" then
		return invalid("status is not an object")
	end
	if decoded.schema ~= 1 then
		return invalid("unsupported status schema")
	end
	local active = decoded.active
	if active ~= nil and not is_null_sentinel(active) and not validate_active(active) then
		return invalid("invalid active recording")
	end
	local sessions = decoded.sessions
	if type(sessions) ~= "table" then
		return invalid("sessions is not an array")
	end
	local session_count = 0
	local highest_index = 0
	for index, session in ipairs(sessions) do
		session_count = session_count + 1
		highest_index = math.max(highest_index, index)
		if not validate_session(session) then
			return invalid("invalid session at index " .. tostring(index))
		end
	end
	for key in pairs(sessions) do
		if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
			return invalid("sessions is not an array")
		end
		highest_index = math.max(highest_index, key)
	end
	if session_count ~= highest_index then
		return invalid("sessions is not an array")
	end
	if active == nil or is_null_sentinel(active) then
		active = nil
	end
	return {
		state = active and active.state or M.STATES.idle,
		active = active and copy_table(active) or nil,
		sessions = sessions,
	}
end

return M
