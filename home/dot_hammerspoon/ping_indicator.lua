-- Hammerspoon ping menu bar runtime: the preferred producer of the one shared
-- ping stream that also feeds tmux_ping.
--
-- Owns a precise 2 s timer, spawns /sbin/ping directly (one process per tick,
-- no shell), pauses while the Mac is locked, claims and writes the shared
-- state file, and renders the styled status item plus a lazy dropdown. The
-- pure window math and presentation model live in ping_window.lua; this module
-- only does scheduling, file I/O, and hs styling. Shared constants mirror
-- home/bin/executable_tmux_ping (and vice versa): change both sides together.
local PingWindow = require("ping_window")

local M = {}

M.NETWORK_SETTINGS_URL = "x-apple.systempreferences:com.apple.Network-Settings.extension"
M.TMP_SUFFIX = ".tmp.hammerspoon"
M.TASK_TIMEOUT_TICKS = 3

if type(BobPingIndicator) ~= "table" then
	BobPingIndicator = {}
end

local runtime = BobPingIndicator

local function default_state_path()
	return os.getenv("HOME") .. "/tmp/" .. PingWindow.STATE_BASENAME
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
	}
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
	if tier == "online" then
		return { hex = PingWindow.OK_COLOR, alpha = 1 }
	elseif tier == "lossy" then
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
	if role == "count" then
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

local function build_menu_items()
	local now = runtime.nowFn()
	local state = read_state_file(runtime.statePath)
	local presentation = PingWindow.presentation(state, now, {
		rtt_ms = runtime.rttMs,
		rtt_sent_at = runtime.rttSentAt,
	})
	local items = {}
	for _, row in ipairs(presentation.menu) do
		if row.kind == "separator" then
			table.insert(items, { title = "-" })
		elseif row.kind == "action" then
			table.insert(items, {
				title = row_text(row),
				fn = function()
					local ok, error_message = xpcall(function()
						hs.urlevent.openURL(M.NETWORK_SETTINGS_URL)
					end, debug.traceback)
					if not ok then
						log_message("network settings failed: %s", error_message)
					end
				end,
			})
		else
			table.insert(items, { title = row_text(row), disabled = true })
		end
	end
	return items
end

local function render_menu_bar()
	local menu = runtime.menu
	if not menu then
		return
	end
	local now = runtime.nowFn()
	local state = read_state_file(runtime.statePath)
	local presentation = PingWindow.presentation(state, now, {
		rtt_ms = runtime.rttMs,
		rtt_sent_at = runtime.rttSentAt,
	})
	local ok, composed = pcall(compose_title, presentation)
	if ok and composed ~= nil then
		menu:setTitle(composed)
	else
		menu:setTitle(presentation.title)
	end
	menu:setTooltip(presentation.tooltip)
	menu:setMenu(function()
		local menu_ok, items = xpcall(build_menu_items, debug.traceback)
		if not menu_ok then
			log_message("menu failed: %s", items)
			return {}
		end
		return items
	end)
	menu:returnToMenuBar()
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

local function ping_completed(task, sent_at, exit_code, std_out)
	if runtime.task ~= task then
		return
	end
	runtime.task = nil
	runtime.taskStartedAt = nil
	runtime.taskSentAt = nil
	-- Re-read the file so the read-modify-write is one synchronous step.
	local fresh = read_state_file(runtime.statePath)
	local results = PingWindow.append_sample(fresh, exit_code == 0, sent_at)
	runtime.rttMs = PingWindow.parse_rtt_ms(std_out)
	runtime.rttSentAt = sent_at
	local now = runtime.nowFn()
	if
		not write_state_file(runtime.statePath, {
			heartbeat = now,
			producer = "hammerspoon",
			sampled = sent_at,
			results = results,
		})
	then
		log_message("ping result not written")
	end
	render_menu_bar()
end

local function ping_tick()
	local now = runtime.nowFn()
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
	task = hs.task.new(runtime.pingPath, on_completion, PingWindow.PING_ARGS)
	if not task then
		log_message("ping task could not be created")
		render_menu_bar()
		return
	end
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
		else
			log_message("ping task start failed: %s", start_result)
		end
		render_menu_bar()
	end
end

-- Start (or restart) the producer loop. All options are optional and exist for
-- tests: state_path, ping_path, and now (a clock function, default os.time).
function M.start(options)
	options = options or {}
	runtime.statePath = options.state_path or default_state_path()
	runtime.pingPath = options.ping_path or PingWindow.PING_PATH
	runtime.nowFn = options.now or os.time
	runtime.rttMs = nil
	runtime.rttSentAt = nil

	stop_runtime_object("timer", runtime.timer)
	stop_runtime_object("task", runtime.task)
	runtime.timer = nil
	runtime.task = nil
	runtime.taskStartedAt = nil
	runtime.taskSentAt = nil

	runtime.menu = runtime.menu or hs.menubar.new(true, "BobPingIndicator")

	run_guarded("initial tick", ping_tick)
	runtime.timer = hs.timer.new(PingWindow.INTERVAL_SECONDS, guarded_callback("tick", ping_tick), true)
	runtime.timer:start()
end

return M
