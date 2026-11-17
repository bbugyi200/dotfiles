-- Hammerspoon ping menu bar runtime: the preferred producer of the one shared
-- ping stream that also feeds tmux_ping.
--
-- Owns a precise 2 s timer, spawns /sbin/ping directly (one process per tick,
-- no shell), pauses while the Mac is locked, claims and writes the shared
-- state file, and renders the styled status item plus a lazy dropdown. The
-- window size comes from ~/.config/ping_window/config (re-read every tick).
-- The pure window math and presentation model live in ping_window.lua; this
-- module only does scheduling, file I/O, and hs styling. Shared constants
-- mirror home/bin/executable_tmux_ping (and vice versa): change both sides
-- together.
local PingWindow = require("ping_window")

local M = {}

M.NETWORK_SETTINGS_URL = "x-apple.systempreferences:com.apple.Network-Settings.extension"
-- Bundle ID for macOS System Settings. This deep link has no "://" delimiter, so
-- hs.urlevent.openURL rejects it before contacting macOS; openURLWithBundle
-- passes the URL to NSURL/NSWorkspace without that check.
M.SYSTEM_SETTINGS_BUNDLE_ID = "com.apple.systempreferences"
M.TMP_SUFFIX = ".tmp.hammerspoon"
M.TASK_TIMEOUT_TICKS = 3
M.PROBE_LOG_COOLDOWN_SECONDS = 600

if type(BobPingIndicator) ~= "table" then
	BobPingIndicator = {}
end

local runtime = BobPingIndicator

local function default_state_path()
	return os.getenv("HOME") .. "/tmp/" .. PingWindow.STATE_BASENAME
end

local function default_events_path()
	return os.getenv("HOME") .. "/tmp/" .. PingWindow.EVENTS_BASENAME
end

local function log_message(format, ...)
	hs.printf("Bob ping " .. format, ...)
end

local function stop_runtime_object(name, object)
	if not object then
		return
	end

	local ok, error_message = xpcall(function()
		if object.stop then
			object:stop()
		elseif object.terminate then
			object:terminate()
		end
	end, debug.traceback)
	if not ok then
		log_message("could not stop previous %s: %s", name, error_message)
	end
end

local function read_state_file(path)
	local handle = io.open(path, "r")
	if not handle then
		return nil
	end
	local text = handle:read("*a")
	handle:close()
	return PingWindow.parse_state(text)
end

local function refresh_window_size()
	local window_size = PingWindow.DEFAULT_WINDOW_SIZE
	local problem = nil
	local handle = io.open(runtime.configPath, "r")
	if handle then
		local text = handle:read("*a")
		handle:close()
		if text ~= nil then
			window_size, problem = PingWindow.parse_config(text)
		end
	end
	runtime.windowSize = window_size
	if problem ~= nil then
		if problem ~= runtime.configProblem then
			log_message("%s", problem)
		end
		runtime.configProblem = problem
	else
		runtime.configProblem = nil
	end
end

local function ensure_parent_directory(path)
	local directory = path:match("^(.*)/[^/]*$")
	if not directory or directory == "" then
		return true
	end
	local attrs_ok, attributes = pcall(function()
		return hs.fs.attributes(directory)
	end)
	if attrs_ok and attributes then
		return true
	end
	local mkdir_ok, made = pcall(function()
		return hs.fs.mkdir(directory)
	end)
	return mkdir_ok and made and true or false
end

-- Atomically replace the state file with one contract line. Returns false (and
-- logs) when nothing could be written; callers treat that as "no claim", so a
-- failed write never blocks tmux from taking over the stream.
local function write_state_file(path, state)
	if not ensure_parent_directory(path) then
		log_message("could not create state directory for %s", path)
		return false
	end
	local tmp_path = path .. M.TMP_SUFFIX
	local handle = io.open(tmp_path, "w")
	if not handle then
		log_message("could not open %s for writing", tmp_path)
		return false
	end
	handle:write(PingWindow.serialize_state(state))
	handle:close()
	local renamed = os.rename(tmp_path, path)
	if not renamed then
		log_message("could not replace %s", path)
		pcall(os.remove, tmp_path)
		return false
	end
	return true
end

local function heartbeat_claim(now, state)
	return {
		heartbeat = now,
		producer = "hammerspoon",
		sampled = (state and state.sampled) or 0,
		results = (state and state.results) or "",
		rtt = state and state.rtt or nil,
		web = state and state.web or nil,
		check = state and state.check or nil,
	}
end

local function event_timestamp(now)
	local value = os.date("%Y-%m-%dT%H:%M:%S%z", now)
	return value:gsub("([+-]%d%d)(%d%d)$", "%1:%2")
end

local function event_quote(value)
	value = tostring(value or "")
	value = value:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("[\r\n\t]", " ")
	return '"' .. value .. '"'
end

local function read_event_lines(path)
	local handle = io.open(path, "r")
	if not handle then
		return {}, false
	end
	local text = handle:read("*a") or ""
	handle:close()
	local lines = {}
	for line in (text .. "\n"):gmatch("(.-)\n") do
		if line ~= "" then
			table.insert(lines, line)
		end
	end
	return lines, true
end

local function event_log_error(reason)
	if runtime.eventLogErrorReported then
		return
	end
	runtime.eventLogErrorReported = true
	log_message("event log unavailable: %s", reason)
end

local function write_event_lines(path, lines)
	if not ensure_parent_directory(path) then
		return false, "could not create parent directory"
	end
	local tmp_path = path .. M.TMP_SUFFIX
	local handle = io.open(tmp_path, "w")
	if not handle then
		return false, "could not open temporary log"
	end
	for _, line in ipairs(lines) do
		handle:write(line, "\n")
	end
	handle:close()
	local renamed = os.rename(tmp_path, path)
	if not renamed then
		pcall(os.remove, tmp_path)
		return false, "could not replace log"
	end
	return true
end

local function trim_event_log(path, keep_lines)
	local lines, exists = read_event_lines(path)
	if not exists then
		runtime.eventLineCount = 0
		return true
	end
	if #lines > keep_lines then
		local newest = {}
		for index = #lines - keep_lines + 1, #lines do
			table.insert(newest, lines[index])
		end
		local ok, reason = write_event_lines(path, newest)
		if not ok then
			event_log_error(reason)
			return false
		end
		lines = newest
	end
	runtime.eventLineCount = #lines
	return true
end

local function append_event(event, detail, now)
	local line = event_timestamp(now or runtime.nowFn()) .. "\t" .. event .. "\t" .. detail
	log_message("event %s", line)
	local path = runtime.eventsPath
	if not path then
		return
	end
	if not ensure_parent_directory(path) then
		event_log_error("could not create parent directory")
		return
	end
	local handle = io.open(path, "a")
	if not handle then
		event_log_error("could not open log for append")
		return
	end
	handle:write(line, "\n")
	handle:close()
	runtime.eventLineCount = (runtime.eventLineCount or 0) + 1
	if runtime.eventLineCount > PingWindow.EVENTS_MAX_LINES then
		trim_event_log(path, PingWindow.EVENTS_KEEP_LINES)
	end
end

local function log_probe(tool, exit_code, reason, now)
	local key = tostring(exit_code == nil and "launch" or exit_code)
	runtime.probeLoggedAt = runtime.probeLoggedAt or {}
	local last = runtime.probeLoggedAt[key]
	if last and now - last < M.PROBE_LOG_COOLDOWN_SECONDS then
		return
	end
	runtime.probeLoggedAt[key] = now
	append_event("probe", "tool=" .. tool .. " exit=" .. key .. " reason=" .. event_quote(reason), now)
end

-- Locked means the Metal session is locked or we are off the console. An
-- error or a nil answer fails open (not paused): pings are cheap, and a stuck
-- "paused" would silently starve both displays.
local function session_paused()
	local ok, properties = pcall(function()
		return hs.caffeinate.sessionProperties()
	end)
	if not ok or type(properties) ~= "table" then
		return false
	end
	return properties.CGSSessionScreenIsLocked == true or properties.kCGSSessionOnConsoleKey == false
end

local function task_in_flight(task)
	if task == nil then
		return false
	end
	if type(task.isRunning) == "function" then
		local ok, running = pcall(function()
			return task:isRunning()
		end)
		if ok then
			return running
		end
	end
	return true
end

local menu_bar_font = hs.styledtext.defaultFonts.menuBar

local label_color = { list = "System", name = "labelColor", alpha = 1 }
local secondary_label_color = { list = "System", name = "secondaryLabelColor", alpha = 1 }

local function valid_font(font)
	if type(font) ~= "table" or type(font.name) ~= "string" or font.name == "" then
		return nil
	end
	if type(hs.styledtext.validFont) ~= "function" or not hs.styledtext.validFont(font.name) then
		return nil
	end
	return font
end

local function font_with_menu_bar_size(name)
	local font = { name = name }
	if type(menu_bar_font) == "table" and menu_bar_font.size then
		font.size = menu_bar_font.size
	end
	return font
end

local function resolve_bold_menu_bar_font()
	local converted = hs.styledtext.convertFont(menu_bar_font, hs.styledtext.fontTraits.boldFont)
	local valid = valid_font(converted)
	if valid then
		return valid
	end
	for _, name in ipairs({ "Helvetica-Bold", "HelveticaNeue-Bold", "Arial-BoldMT" }) do
		local fallback = valid_font(font_with_menu_bar_size(name))
		if fallback then
			return fallback
		end
	end
	return nil
end

local function resolve_mono_menu_bar_font()
	for _, name in ipairs({ "Menlo-Regular", "Menlo", "Monaco" }) do
		local fallback = valid_font(font_with_menu_bar_size(name))
		if fallback then
			return fallback
		end
	end
	return nil
end

local bold_menu_bar_font = resolve_bold_menu_bar_font()
local mono_menu_bar_font = resolve_mono_menu_bar_font() or menu_bar_font

local function glyph_color(tier)
	if tier == "online" or tier == "web" then
		return { hex = PingWindow.OK_COLOR, alpha = 1 }
	elseif tier == "lossy" or tier == "slow" then
		return { hex = PingWindow.WARN_COLOR, alpha = 1 }
	elseif tier == "down" or tier == "offline" then
		return { hex = PingWindow.ALERT_COLOR, alpha = 1 }
	end
	return secondary_label_color
end

-- Map tier plus segment role to hs.styledtext attributes. The count uses Menlo
-- regular at the menu bar size; glyph and pads use the default menu bar font.
-- Nothing is bold except the offline pill, so the Pomodoro countdown stays the
-- visual primary.
local function title_attributes(tier, role)
	if tier == "offline" then
		return {
			color = { hex = PingWindow.BADGE_TEXT_COLOR, alpha = 1 },
			font = bold_menu_bar_font,
			backgroundColor = { hex = PingWindow.ALERT_COLOR, alpha = 1 },
		}
	end
	if role == "note" then
		return { color = secondary_label_color, font = menu_bar_font }
	end
	if role == "count" or role == "latency" then
		if tier == "down" then
			return { color = { hex = PingWindow.ALERT_COLOR, alpha = 1 }, font = mono_menu_bar_font }
		elseif tier == "stale" then
			return { color = secondary_label_color, font = mono_menu_bar_font }
		end
		return { color = label_color, font = mono_menu_bar_font }
	elseif role == "glyph" then
		return { color = glyph_color(tier), font = menu_bar_font }
	end
	return { color = label_color, font = menu_bar_font }
end

local function compose_title(presentation)
	local composed = nil
	for _, segment in ipairs(presentation.segments) do
		local styled = hs.styledtext.new(segment.text, title_attributes(presentation.tier, segment.role))
		if composed == nil then
			composed = styled
		else
			composed = composed .. styled
		end
	end
	if composed == nil then
		error("empty title segments")
	end
	return composed
end

local function row_text(row)
	local parts = {}
	for _, segment in ipairs(row.segments or {}) do
		table.insert(parts, segment.text)
	end
	return table.concat(parts)
end

local function open_network_settings()
	local ok, result = xpcall(function()
		return hs.urlevent.openURLWithBundle(M.NETWORK_SETTINGS_URL, M.SYSTEM_SETTINGS_BUNDLE_ID)
	end, debug.traceback)
	if not ok then
		log_message("network settings failed: %s (%s)", M.NETWORK_SETTINGS_URL, result)
		hs.alert.show("Network Settings could not be opened — open System Settings → Network manually")
		return false
	end
	if result ~= true then
		log_message("network settings failed: %s returned %s", M.NETWORK_SETTINGS_URL, tostring(result))
		hs.alert.show("Network Settings could not be opened — open System Settings → Network manually")
		return false
	end
	return true
end

local function build_menu_items()
	local now = runtime.nowFn()
	local state = read_state_file(runtime.statePath)
	local presentation = PingWindow.presentation(state, now, {
		window_size = runtime.windowSize or PingWindow.DEFAULT_WINDOW_SIZE,
		web_detail = runtime.webDetail,
	})
	local items = {}
	for _, row in ipairs(presentation.menu) do
		if row.kind == "separator" then
			table.insert(items, { title = "-" })
		elseif row.kind == "action" then
			table.insert(items, {
				title = row_text(row),
				fn = function()
					open_network_settings()
				end,
			})
		else
			table.insert(items, { title = row_text(row), disabled = true })
		end
	end
	return items
end

local function menu_builder()
	local menu_ok, items = xpcall(build_menu_items, debug.traceback)
	if not menu_ok then
		log_message("menu failed: %s", items)
		return {}
	end
	return items
end

local function log_tier_transition(state, presentation, now)
	if runtime.lastTier == presentation.tier then
		return
	end
	local assessment = PingWindow.assess(state, now, runtime.windowSize or PingWindow.DEFAULT_WINDOW_SIZE)
	local summary = assessment.summary
	local median = "-"
	if state and state.rtt and #state.rtt >= PingWindow.SLOW_MIN_REPLIES then
		median = tostring(PingWindow.upper_median(state.rtt))
	end
	local web = "-"
	if state and state.web then
		web = string.format("%s,%d,%s", state.web.verdict, state.web.at, state.web.ms or "-")
	end
	local check = state and state.check and tostring(state.check) or "-"
	local previous = runtime.lastTier or "unknown"
	local detail = string.format(
		"transition=%s→%s title=%s replies=%d/%d trailing=%d median=%s web=%s check=%s producer=%s",
		previous,
		presentation.tier,
		event_quote(presentation.title),
		summary.successes,
		summary.total,
		summary.trailing,
		median,
		web,
		check,
		(state and state.producer) or "unknown"
	)
	runtime.lastTier = presentation.tier
	append_event("tier", detail, now)
end

local function render_menu_bar()
	local menu = runtime.menu
	if not menu then
		return
	end
	local now = runtime.nowFn()
	local state = read_state_file(runtime.statePath)
	local presentation = PingWindow.presentation(state, now, {
		window_size = runtime.windowSize or PingWindow.DEFAULT_WINDOW_SIZE,
		web_detail = runtime.webDetail,
	})
	log_tier_transition(state, presentation, now)
	local ok, composed = pcall(compose_title, presentation)
	if ok and composed ~= nil then
		menu:setTitle(composed)
	else
		menu:setTitle(presentation.title)
	end
	menu:setTooltip(presentation.tooltip)
end

local function run_guarded(context, callback, ...)
	local args = { n = select("#", ...), ... }
	local unpack_args = table.unpack or unpack
	local ok, result = xpcall(function()
		return callback(unpack_args(args, 1, args.n))
	end, debug.traceback)
	if not ok then
		log_message("%s failed: %s", context, result)
	end
	return ok, result
end

local function guarded_callback(context, callback)
	return function(...)
		run_guarded(context, callback, ...)
	end
end

local function web_completed(task, exit_code, std_out)
	if runtime.webTask ~= task then
		return
	end
	runtime.webTask = nil
	runtime.webTaskStartedAt = nil
	local now = runtime.nowFn()
	local fresh = read_state_file(runtime.statePath)
	local verdict, problem = PingWindow.web_outcome(exit_code, std_out, now)
	local next_state = heartbeat_claim(now, fresh)
	next_state.check = nil
	if verdict == nil then
		log_probe("curl", exit_code, problem, now)
		if not write_state_file(runtime.statePath, next_state) then
			log_message("web result not written")
		end
		render_menu_bar()
		return
	end

	local previous_verdict = fresh and fresh.web and fresh.web.verdict or nil
	next_state.web = {
		verdict = verdict.verdict,
		at = verdict.at,
		ms = verdict.ms,
	}
	runtime.webDetail = {
		at = verdict.at,
		reason = verdict.reason,
		http_code = verdict.http_code,
		exit_code = exit_code,
	}
	if previous_verdict ~= verdict.verdict then
		append_event(
			"web",
			string.format(
				"verdict=%s ms=%s http=%s exit=%s reason=%s",
				verdict.verdict,
				verdict.ms or "-",
				verdict.http_code or "-",
				exit_code == nil and "-" or tostring(exit_code),
				event_quote(verdict.reason or "-")
			),
			now
		)
	end
	if not write_state_file(runtime.statePath, next_state) then
		log_message("web result not written")
	end
	render_menu_bar()
end

local function web_check_allowed(state, sample, now)
	if sample ~= "0" or task_in_flight(runtime.webTask) or session_paused() then
		return false
	end
	if state and state.check and now >= state.check and now - state.check <= PingWindow.WEB_CHECK_GRACE_SECONDS then
		return false
	end
	local last_started = runtime.webStartedAt
	if last_started == nil and state and state.web then
		last_started = state.web.at
	end
	return last_started == nil or now - last_started >= PingWindow.WEB_RECHECK_SECONDS
end

local function create_web_task(now)
	runtime.webStartedAt = now
	local task = nil
	local completion = guarded_callback("web task completion", function(exit_code, std_out, std_err)
		web_completed(task, exit_code, std_out, std_err)
	end)
	local ok, result = xpcall(function()
		return hs.task.new(PingWindow.CURL_PATH, completion, PingWindow.CURL_ARGS)
	end, debug.traceback)
	if not ok or result == nil then
		log_probe("curl", nil, ok and "curl task could not be created" or result, now)
		return nil
	end
	task = result
	return task
end

local function start_web_task(task, now, state)
	runtime.webTask = task
	runtime.webTaskStartedAt = now
	local start_ok, start_result = xpcall(function()
		return task:start()
	end, debug.traceback)
	if start_ok and start_result then
		return true
	end
	runtime.webTask = nil
	runtime.webTaskStartedAt = nil
	local reason = start_ok and "curl task could not be started" or start_result
	log_probe("curl", nil, reason, now)
	local next_state = heartbeat_claim(now, state)
	next_state.check = nil
	if not write_state_file(runtime.statePath, next_state) then
		log_message("web launch failure not written")
	end
	return false
end

local function ping_completed(task, sent_at, exit_code, std_out)
	if runtime.task ~= task then
		return
	end
	runtime.task = nil
	runtime.taskStartedAt = nil
	runtime.taskSentAt = nil
	-- Re-read the file so the read-modify-write is one synchronous step.
	local fresh = read_state_file(runtime.statePath)
	local sample, rtt_or_problem = PingWindow.ping_outcome(exit_code, std_out)
	local now = runtime.nowFn()
	if sample == nil then
		log_probe("ping", exit_code, rtt_or_problem, now)
		if not write_state_file(runtime.statePath, heartbeat_claim(now, fresh)) then
			log_message("ping tool error claim not written")
		end
		render_menu_bar()
		return
	end

	local results =
		PingWindow.append_sample(fresh, sample, sent_at, runtime.windowSize or PingWindow.DEFAULT_WINDOW_SIZE)
	local next_state = {
		heartbeat = now,
		producer = "hammerspoon",
		sampled = sent_at,
		results = results,
		rtt = PingWindow.append_rtt(
			fresh,
			rtt_or_problem,
			sent_at,
			runtime.windowSize or PingWindow.DEFAULT_WINDOW_SIZE
		),
		web = fresh and fresh.web or nil,
		check = fresh and fresh.check or nil,
	}
	local web_task = nil
	if web_check_allowed(fresh, sample, now) then
		web_task = create_web_task(now)
		if web_task then
			next_state.check = now
		end
	end
	if not write_state_file(runtime.statePath, next_state) then
		if web_task then
			stop_runtime_object("web task", web_task)
		end
		log_message("ping result not written")
		render_menu_bar()
		return
	end
	if web_task then
		start_web_task(web_task, now, next_state)
	end
	render_menu_bar()
end

local function stop_expired_web_task(now)
	local task = runtime.webTask
	local started = runtime.webTaskStartedAt
	if not task_in_flight(task) or not started or now - started <= PingWindow.WEB_CHECK_GRACE_SECONDS then
		return false
	end
	runtime.webTask = nil
	runtime.webTaskStartedAt = nil
	stop_runtime_object("web task", task)
	local fresh = read_state_file(runtime.statePath)
	if fresh and fresh.check == started then
		local next_state = heartbeat_claim(now, fresh)
		next_state.check = nil
		if not write_state_file(runtime.statePath, next_state) then
			log_message("expired web check claim not written")
		end
	end
	log_probe("curl", "grace", "web task exceeded its grace period", now)
	render_menu_bar()
	return true
end

local function ping_tick()
	refresh_window_size()
	local now = runtime.nowFn()
	stop_expired_web_task(now)
	if task_in_flight(runtime.task) then
		local timeout = PingWindow.INTERVAL_SECONDS * M.TASK_TIMEOUT_TICKS
		local elapsed = runtime.taskStartedAt and (now - runtime.taskStartedAt) or 0
		if elapsed >= timeout then
			local stuck = runtime.task
			runtime.task = nil
			runtime.taskStartedAt = nil
			runtime.taskSentAt = nil
			local ok, error_message = xpcall(function()
				stuck:terminate()
			end, debug.traceback)
			if not ok then
				log_message("could not terminate stuck ping: %s", error_message)
			else
				log_message("terminated a ping running for %d s", elapsed)
			end
		end
		return
	end

	local state = read_state_file(runtime.statePath)

	-- While locked, keep the heartbeat fresh (so tmux does not take over and
	-- ping) but send nothing: neither display is visible then.
	if session_paused() then
		if not write_state_file(runtime.statePath, heartbeat_claim(now, state)) then
			log_message("heartbeat claim not written while paused")
		end
		render_menu_bar()
		return
	end

	-- A tmux client just pinged: claim the stream so tmux backs off on its
	-- next redraw, and skip our own ping.
	if state and state.producer == "tmux" and now - state.sampled < PingWindow.INTERVAL_SECONDS then
		write_state_file(runtime.statePath, heartbeat_claim(now, state))
		render_menu_bar()
		return
	end

	local sent_at = now
	local task = nil
	local on_completion = guarded_callback("task completion", function(exit_code, std_out, std_err)
		ping_completed(task, sent_at, exit_code, std_out)
	end)
	local create_ok, created_task = xpcall(function()
		return hs.task.new(runtime.pingPath, on_completion, PingWindow.PING_ARGS)
	end, debug.traceback)
	if not create_ok or not created_task then
		log_message("ping task could not be created")
		log_probe("ping", nil, create_ok and "ping task could not be created" or created_task, now)
		render_menu_bar()
		return
	end
	task = created_task
	runtime.task = task
	runtime.taskStartedAt = now
	runtime.taskSentAt = sent_at
	local start_ok, start_result = xpcall(function()
		return task:start()
	end, debug.traceback)
	if not start_ok or not start_result then
		runtime.task = nil
		runtime.taskStartedAt = nil
		runtime.taskSentAt = nil
		if start_ok then
			log_message("ping task could not be started")
			log_probe("ping", nil, "ping task could not be started", now)
		else
			log_message("ping task start failed: %s", start_result)
			log_probe("ping", nil, start_result, now)
		end
		render_menu_bar()
	end
end

-- Start (or restart) the producer loop. All options are optional and exist for
-- tests: state_path, events_path, ping_path, config_path, and now (a clock
-- function, default os.time).
function M.start(options)
	options = options or {}
	local previous_timer = runtime.timer
	local previous_ping_task = runtime.task
	local previous_web_task = runtime.webTask
	local previous_web_started_at = runtime.webStartedAt
	-- Detach first so callbacks caused by stop/terminate cannot write stale data.
	runtime.timer = nil
	runtime.task = nil
	runtime.webTask = nil
	runtime.taskStartedAt = nil
	runtime.taskSentAt = nil
	runtime.webTaskStartedAt = nil
	stop_runtime_object("timer", previous_timer)
	stop_runtime_object("task", previous_ping_task)
	stop_runtime_object("web task", previous_web_task)

	runtime.statePath = options.state_path or default_state_path()
	runtime.eventsPath = options.events_path or default_events_path()
	runtime.pingPath = options.ping_path or PingWindow.PING_PATH
	runtime.configPath = options.config_path or (os.getenv("HOME") .. "/" .. PingWindow.CONFIG_RELATIVE_PATH)
	runtime.nowFn = options.now or os.time
	runtime.webDetail = nil
	runtime.windowSize = PingWindow.DEFAULT_WINDOW_SIZE
	runtime.configProblem = nil
	runtime.probeLoggedAt = runtime.probeLoggedAt or {}
	runtime.eventLogErrorReported = runtime.eventLogErrorReported or false
	runtime.eventLineCount = 0

	local now = runtime.nowFn()
	local previous_state = read_state_file(runtime.statePath)
	runtime.webStartedAt = previous_web_started_at
		or (previous_state and (previous_state.check or (previous_state.web and previous_state.web.at)))
		or nil
	if previous_state and previous_state.check then
		local cleared = heartbeat_claim(now, previous_state)
		cleared.check = nil
		if not write_state_file(runtime.statePath, cleared) then
			log_message("stale web check claim not cleared on start")
		end
	end
	refresh_window_size()
	trim_event_log(runtime.eventsPath, PingWindow.EVENTS_KEEP_LINES)

	runtime.menu = runtime.menu or hs.menubar.new(true, "BobPingIndicator")

	-- Install the lazy builder once per load, never from a render, tick, or
	-- task path. Calling setMenu while the menu is open empties and detaches
	-- the open NSMenu (which closes the dropdown), and timers keep firing
	-- while a menu is open.
	runtime.menu:setMenu(menu_builder)
	runtime.menu:returnToMenuBar()
	append_event(
		"start",
		string.format(
			"args=%s window_size=%d state=v2",
			event_quote(table.concat(PingWindow.PING_ARGS, " ")),
			runtime.windowSize
		),
		now
	)

	run_guarded("initial tick", ping_tick)
	runtime.timer = hs.timer.new(PingWindow.INTERVAL_SECONDS, guarded_callback("tick", ping_tick), true)
	runtime.timer:start()
end

return M
