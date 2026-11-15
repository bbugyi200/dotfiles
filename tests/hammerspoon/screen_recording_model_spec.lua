local MODEL_PATH = "home/dot_hammerspoon/screen_recording_model.lua"
local model = assert(loadfile(MODEL_PATH))()

local function effect_of(effects, kind)
	for _, item in ipairs(effects) do
		if item.type == kind then
			return item
		end
	end
	return nil
end

local function state(state_name, fields)
	local result = fields or {}
	result.state = state_name
	return result
end

local function rect(x, y, w, h)
	return { x = x, y = y, w = w, h = h }
end

local function status_session(overrides)
	local result = {
		schema = 1,
		id = "session",
		name = "clip",
		status = "done",
		region = rect(20, 30, 800, 450),
		mic = false,
		probe = false,
		started_at = 100,
		cap_seconds = 600,
		orphaned = false,
		acked = { notified = false, adopted = false },
		log = "/tmp/macrec/session/log",
		hosts = { apollo = "ok", athena = "ok" },
		host_detail = {},
	}
	for key, value in pairs(overrides or {}) do
		result[key] = value
	end
	return result
end

local function separated_by_gap(item, region, gap)
	local right = region.x + region.w
	local bottom = region.y + region.h
	return item.x + item.w <= region.x - gap + 0.001
		or item.x >= right + gap - 0.001
		or item.y + item.h <= region.y - gap + 0.001
		or item.y >= bottom + gap - 0.001
end

describe("screen recording model constants", function()
	it("uses the selected chord and shared visual timings", function()
		assert.same({ mods = { "ctrl", "alt", "shift" }, key = "v" }, model.CHORD)
		assert.equals("⌃⌥⇧V", model.CHORD_LABEL)
		assert.equals("#E3413B", model.ACCENT)
		assert.equals("#FF9F0A", model.WARN)
		assert.equals("#30d158", model.OK)
		assert.equals(600, model.CAP_SECONDS)
		assert.equals(540, model.WARN_AT)
		assert.equals(0.15, model.DEBOUNCE)
		assert.equals(4, model.CHROME_GAP)
		assert.equals("macrecLastRegion", model.SETTINGS_KEY)
		assert.equals("macscrotLastRegion", model.FALLBACK_SETTINGS_KEY)
	end)
end)

describe("screen recording reducer", function()
	it("opens the selector from idle and cancels it with the chord", function()
		local selecting, effects = model.reduce(state("idle"), { type = "chord" }, 1)
		assert.equals("selecting", selecting.state)
		local open = assert(effect_of(effects, "open_selector"))
		assert.equals(model.SETTINGS_KEY, open.settings_key)
		assert.equals(model.FALLBACK_SETTINGS_KEY, open.fallback_settings_key)

		local idle, cancel_effects = model.reduce(selecting, { type = "chord" }, 2)
		assert.equals("idle", idle.state)
		assert.is_truthy(effect_of(cancel_effects, "close_selector"))
	end)

	it("debounces a paired picker and hotkey chord and ignores autorepeat", function()
		local selecting = model.reduce(state("idle"), { type = "chord" }, 10)
		local still_selecting, effects = model.reduce(selecting, { type = "chord" }, 10.1)
		assert.equals("selecting", still_selecting.state)
		assert.equals(0, #effects)
		local repeat_model, repeat_effects = model.reduce(selecting, { type = "chord", ["repeat"] = true }, 11)
		assert.equals("selecting", repeat_model.state)
		assert.equals(0, #repeat_effects)
		local idle = model.reduce(selecting, { type = "chord" }, 10.16)
		assert.equals("idle", idle.state)
	end)

	it("starts from a valid selection and records the mic and save-default choice", function()
		local selecting = state("selecting")
		local starting, effects = model.reduce(selecting, {
			type = "enter",
			region = rect(20, 30, 800, 450),
			mic = true,
			command_enter = true,
		}, 100)
		assert.equals("starting", starting.state)
		assert.is_truthy(effect_of(effects, "close_selector"))
		local start = assert(effect_of(effects, "start_recorder"))
		assert.same(rect(20, 30, 800, 450), start.region)
		assert.is_true(start.mic)
		assert.is_true(start.save_default)
		assert.equals(600, start.max_seconds)

		local recording, start_effects = model.reduce(starting, {
			type = "start_ok",
			session = { id = "abc", name = "clip", started_at = 101 },
		}, 101)
		assert.equals("recording", recording.state)
		assert.equals("abc", recording.session.id)
		assert.is_true(recording.session.mic)
		assert.same(rect(20, 30, 800, 450), recording.session.region)
		assert.is_truthy(effect_of(start_effects, "show_chrome"))
	end)

	it("returns idle and notifies when the recorder fails to start", function()
		local starting = state("starting", { selection = { region = rect(0, 0, 40, 30) } })
		local idle, effects = model.reduce(starting, { type = "start_fail", reason = "permission denied" }, 1)
		assert.equals("idle", idle.state)
		local notification = assert(effect_of(effects, "notify")).notification
		assert.equals("Recording didn't start", notification.title)
		assert.equals("permission denied", notification.body)
	end)

	it("discards once the recorder is ready if the chord was pressed while starting", function()
		local starting = state("starting")
		local pending = model.reduce(starting, { type = "chord" }, 1)
		assert.is_true(pending.discardPending)
		local stopping, effects = model.reduce(pending, { type = "start_ok", id = "late" }, 2)
		assert.equals("stopping", stopping.state)
		assert.is_truthy(effect_of(effects, "discard"))
		assert.is_nil(effect_of(effects, "show_chrome"))
	end)

	it("stops on chord and ignores another chord while stopping", function()
		local recording = state("recording", { session = { id = "one" } })
		local stopping, effects = model.reduce(recording, { type = "chord", change_count = 4 }, 1)
		assert.equals("stopping", stopping.state)
		assert.equals(4, stopping.clipboardBaseline)
		assert.is_truthy(effect_of(effects, "flash_shutter"))
		assert.equals("chord", assert(effect_of(effects, "stop_recorder")).reason)
		local unchanged, duplicate_effects = model.reduce(stopping, { type = "chord" }, 2)
		assert.equals("stopping", unchanged.state)
		assert.equals(0, #duplicate_effects)
	end)

	it("applies picker cancellation and ignores Enter outside the selector", function()
		local selecting, effects = model.reduce(state("selecting"), { type = "picker_cancel" }, 1)
		assert.equals("idle", selecting.state)
		assert.is_truthy(effect_of(effects, "close_selector"))
		local unchanged, ignored = model.reduce(state("idle"), { type = "enter", region = rect(1, 1, 5, 5) }, 2)
		assert.equals("idle", unchanged.state)
		assert.equals(0, #ignored)
	end)

	for _, scenario in ipairs({
		{ event = "sleep", reason = "sleep" },
		{ event = "lock", reason = "lock" },
		{ event = "display_loss", reason = "display" },
	}) do
		it("stops for " .. scenario.event, function()
			local recording = state("recording", { session = { id = "one" } })
			local stopping, effects = model.reduce(recording, { type = scenario.event, change_count = 8 }, 5)
			assert.equals("stopping", stopping.state)
			assert.equals(scenario.reason, assert(effect_of(effects, "stop_recorder")).reason)
			assert.equals(8, stopping.clipboardBaseline)
		end)
	end

	it("discards only after confirmation and never moves a discard into shipping", function()
		local recording = state("recording", { session = { id = "discard-me" } })
		local stopping, effects = model.reduce(recording, { type = "discard_confirmed", change_count = 9 }, 2)
		assert.equals("stopping", stopping.state)
		assert.equals("discard", stopping.stopReason)
		assert.equals("discard-me", assert(effect_of(effects, "discard")).session_id)
		local idle = model.reduce(stopping, { type = "recorder_gone", id = "discard-me" }, 3)
		assert.equals("idle", idle.state)
	end)

	it("enters background shipping after stop completion or an external recorder exit", function()
		local stopping = state("stopping", { session = { id = "one" } })
		local shipping, effects = model.reduce(stopping, { type = "stop_done", id = "one" }, 3)
		assert.equals("shipping", shipping.state)
		assert.is_truthy(effect_of(effects, "update_menu"))
		local external = model.reduce(state("recording", { session = { id = "two" } }), {
			type = "recorder_gone",
			id = "two",
			reason = "cap",
		}, 4)
		assert.equals("shipping", external.state)
		assert.equals("cap", external.stopReason)
	end)

	it("ignores events for stale session ids", function()
		local recording = state("recording", { session = { id = "current" } })
		local unchanged, effects = model.reduce(recording, { type = "chord", id = "stale" }, 2)
		assert.equals("recording", unchanged.state)
		assert.equals(0, #effects)
	end)

	it("updates the timer and enforces the cap", function()
		local recording = state("recording", { session = { id = "one", started_at = 100 } })
		local still_recording, effects = model.reduce(recording, { type = "tick" }, 640)
		assert.equals("recording", still_recording.state)
		assert.equals(540, assert(effect_of(effects, "update_menu")).elapsed)
		local stopping, cap_effects = model.reduce(recording, { type = "tick" }, 700)
		assert.equals("stopping", stopping.state)
		assert.equals("cap", assert(effect_of(cap_effects, "stop_recorder")).reason)
	end)

	it("transitions from a status refresh and notifies a terminal session once", function()
		local active = {
			id = "active",
			name = "clip",
			state = "recording",
			region = rect(10, 20, 300, 200),
			mic = false,
			probe = false,
			started_at = 10,
			cap_seconds = 600,
			recorder_alive = true,
		}
		local recording, active_effects = model.reduce(state("idle"), {
			type = "status_refresh",
			status = { state = "recording", active = active, sessions = {} },
		}, 11)
		assert.equals("recording", recording.state)
		assert.is_truthy(effect_of(active_effects, "show_chrome"))

		local done_session = status_session({
			id = "active",
			mp4 = "/tmp/clip.mp4",
			duration_s = 42,
			bytes = 4800000,
		})
		local done, done_effects = model.reduce(recording, {
			type = "status_refresh",
			status = { state = "idle", active = nil, sessions = { done_session } },
			clipboard_change_count = 3,
		}, 60)
		assert.equals("done", done.state)
		assert.is_truthy(effect_of(done_effects, "hide_chrome"))
		-- The baseline is absent, so status adoption never overwrites the clipboard.
		assert.is_truthy(effect_of(done_effects, "notify"))
		assert.is_truthy(effect_of(done_effects, "ack"))
	end)

	it("requests orphan recovery and ignores subsequent duplicate recovery requests", function()
		local orphan = status_session({
			id = "orphan",
			status = "recording",
			orphaned = true,
			recovered = false,
		})
		local shipping, effects = model.reduce(state("idle"), {
			type = "status_refresh",
			status = { state = "idle", sessions = { orphan } },
		}, 1)
		assert.equals("shipping", shipping.state)
		assert.equals("orphan", assert(effect_of(effects, "recover")).session_id)
		local again, again_effects = model.reduce(shipping, {
			type = "status_refresh",
			status = { state = "idle", sessions = { orphan } },
		}, 2)
		assert.equals("shipping", again.state)
		assert.is_nil(effect_of(again_effects, "recover"))
	end)
end)

describe("screen recording chrome geometry", function()
	it("places all strips and bracket segments outside the recording region", function()
		local screen = rect(-500, 0, 1800, 1000)
		local regions = {
			rect(-500, 0, 400, 300),
			rect(900, 700, 400, 300),
			rect(-200, 300, 900, 500),
			rect(-500, 0, 1800, 1000),
		}
		for _, region in ipairs(regions) do
			local layout = model.chromeLayout(region, screen)
			assert.is_truthy(layout.strips.top)
			assert.is_truthy(layout.strips.bottom)
			assert.is_truthy(layout.strips.left)
			assert.is_truthy(layout.strips.right)
			for _, strip in pairs(layout.strips) do
				assert.is_true(separated_by_gap(strip, region, model.CHROME_GAP))
			end
			assert.equals(8, #layout.brackets)
			for _, bracket in ipairs(layout.brackets) do
				assert.is_true(separated_by_gap(bracket, region, model.CHROME_GAP))
			end
			if region.w == screen.w and region.h == screen.h then
				assert.equals("hidden", layout.pill.placement)
			end
		end
	end)

	it("keeps every generated piece outside randomized regions at display edges", function()
		local screen = rect(0, 0, 1440, 900)
		local regions = {
			rect(0, 0, 200, 160),
			rect(1240, 0, 200, 160),
			rect(0, 740, 200, 160),
			rect(1240, 740, 200, 160),
		}
		for index = 1, 80 do
			local x = (index * 137) % 1240
			local y = (index * 71) % 740
			table.insert(regions, rect(x, y, 200, 160))
		end
		for _, region in ipairs(regions) do
			local layout = model.chromeLayout(region, screen)
			for _, strip in pairs(layout.strips) do
				assert.is_true(separated_by_gap(strip, region, model.CHROME_GAP))
			end
			for _, bracket in ipairs(layout.brackets) do
				assert.is_true(separated_by_gap(bracket, region, model.CHROME_GAP))
			end
			if layout.pill.frame then
				assert.is_true(separated_by_gap(layout.pill.frame, region, model.CHROME_GAP))
			end
		end
	end)

	it("chooses the pill placement in the specified priority order", function()
		local screen = rect(0, 0, 1440, 900)
		assert.equals("bottom_right", model.chromeLayout(rect(200, 200, 500, 300), screen).pillPlacement)
		assert.equals("top_right", model.chromeLayout(rect(200, 700, 500, 180), screen).pillPlacement)
		assert.equals("right", model.chromeLayout(rect(900, 20, 300, 860), screen).pillPlacement)
		assert.equals("hidden", model.chromeLayout(rect(0, 0, 1300, 880), screen).pillPlacement)
	end)

	it("returns an empty safe layout for invalid geometry", function()
		local layout = model.chromeLayout(rect(1, 1, -2, 3), rect(0, 0, 10, 10))
		assert.equals("invalid region or screen frame", layout.reason)
		assert.equals(0, #layout.brackets)
		assert.equals("hidden", layout.pillPlacement)
	end)
end)

describe("screen recording presentation helpers", function()
	it("formats elapsed time and warning tone", function()
		assert.equals("0:00", model.formatElapsed(-1))
		assert.equals("9:00", model.formatElapsed(540.9))
		assert.equals("10:00", model.formatElapsed(600))
		assert.equals("accent", model.timerTone(539.9))
		assert.equals("warn", model.timerTone(540))
	end)

	it("builds menu title segments and action rows from the state", function()
		local title = model.menuTitle(
			state("recording", {
				session = { started_at = 100, mic = true },
			}),
			640
		)
		assert.equals("● 9:00 · 1:00 left · MIC", title[1].text)
		assert.equals("warn", title[1].role)
		assert.equals(0, #model.menuTitle("idle", 0))

		local items = model.menuItems(
			state("recording", {
				session = {
					started_at = 100,
					region = rect(0, 0, 1280, 720),
					display_name = "Built-in Retina Display",
					mic = false,
				},
			}),
			142
		)
		assert.equals("header", items[1].kind)
		assert.equals("Stop & Upload  " .. model.CHORD_LABEL, items[3].segments[1].text)
		assert.equals("stop_upload", items[3].action)
		assert.equals("discard", items[4].action)
		local failed = model.menuItems("failed")
		assert.same({ "retry", "reveal", "show_log", "dismiss" }, {
			failed[2].action,
			failed[3].action,
			failed[4].action,
			failed[5].action,
		})
	end)

	it("builds mic-aware selector badge and hint", function()
		assert.equals("● REC · 1280 × 720", model.selectorBadge({ region = rect(0, 0, 1280, 720) }))
		assert.equals(
			"● REC · MIC · 1280 × 720",
			model.selectorBadge({ region = rect(0, 0, 1280, 720), mic = true })
		)
		assert.is_truthy(model.selectorHint({ mic = false }):find("M: mic off", 1, true))
		assert.is_truthy(model.selectorHint({ mic = true }):find("M: mic on", 1, true))
		assert.is_truthy(model.selectorHint({}):find("F: full screen · W: window", 1, true))
		assert.is_truthy(model.selectorHint({}):find("Esc or " .. model.CHORD_LABEL .. ": cancel", 1, true))
	end)

	it("formats host outcomes, byte sizes, and clipboard decisions", function()
		assert.equals("Apollo + Athena", model.hostsLabel({ apollo = "ok", athena = "ok" }))
		assert.equals("Athena · apollo failed", model.hostsLabel({ apollo = "failed", athena = "ok" }))
		assert.equals(
			"Athena · apollo skipped (low disk)",
			model.hostsLabel({ apollo = "skipped", athena = "ok" }, { apollo = "low disk" })
		)
		assert.equals("4.8 MB", model.formatBytes(4800000))
		assert.equals("0 B", model.formatBytes(-1))
		assert.is_true(model.clipboardDecision(4, 4, false))
		assert.is_false(model.clipboardDecision(4, 5, false))
		assert.is_false(model.clipboardDecision(4, 4, true))
		assert.is_false(model.clipboardDecision(nil, nil, false))
	end)

	it("builds the normal, partial, skipped, cap, recovered, and failed notifications", function()
		local base = {
			id = "done",
			name = "clip",
			status = "done",
			mp4 = "~/tmp/screencasts/clip.mp4",
			duration_s = 42,
			bytes = 4800000,
			hosts = { apollo = "ok", athena = "ok" },
		}
		local done = model.notification(base, { copied = true })
		assert.equals("done", done.kind)
		assert.equals("Recording uploaded", done.title)
		assert.equals("Reveal", done.action)
		assert.is_truthy(done.body:find("path copied", 1, true))

		local partial_session = {}
		for key, value in pairs(base) do
			partial_session[key] = value
		end
		partial_session.hosts = { apollo = "failed", athena = "ok" }
		local partial = model.notification(partial_session, {})
		assert.equals("partial", partial.kind)
		assert.is_truthy(partial.subtitle:find("Athena · apollo failed", 1, true))

		local skipped_session = {}
		for key, value in pairs(base) do
			skipped_session[key] = value
		end
		skipped_session.hosts = { apollo = "skipped", athena = "ok" }
		skipped_session.host_detail = { apollo = "low disk" }
		local skipped = model.notification(skipped_session, {})
		assert.equals("skipped", skipped.kind)
		assert.is_truthy(skipped.subtitle:find("apollo skipped (low disk)", 1, true))

		local cap_session = {}
		for key, value in pairs(base) do
			cap_session[key] = value
		end
		cap_session.stop_reason = "cap"
		cap_session.duration_s = 600
		local capped = model.notification(cap_session, { copied = true })
		assert.is_truthy(capped.subtitle:find("Stopped at 10:00 cap", 1, true))

		local recovered = model.notification(base, { recovered = true })
		assert.equals("Recovered recording uploaded", recovered.title)

		local failed_session = {}
		for key, value in pairs(base) do
			failed_session[key] = value
		end
		failed_session.status = "failed"
		failed_session.hosts = { apollo = "failed", athena = "failed" }
		local failed = model.notification(failed_session, {})
		assert.equals("failed", failed.kind)
		assert.equals("Recording not uploaded", failed.title)
		assert.is_truthy(failed.body:find("Saved locally:", 1, true))
		assert.is_truthy(failed.body:find("Retry from the menu bar", 1, true))
	end)
end)

describe("screen recording status parser", function()
	local valid_active = {
		id = "live",
		name = "clip",
		state = "recording",
		region = rect(20, 30, 800, 450),
		mic = false,
		probe = false,
		started_at = 100,
		cap_seconds = 600,
		recorder_alive = true,
	}

	it("accepts schema 1 active and session data", function()
		local parsed = model.parseStatus({ schema = 1, active = valid_active, sessions = {} })
		assert.equals("recording", parsed.state)
		assert.same(valid_active, parsed.active)
		assert.equals(0, #parsed.sessions)
		local no_active = model.parseStatus({ schema = 1, sessions = {} })
		assert.equals("idle", no_active.state)
	end)

	it("degrades malformed top-level data and unsupported schemas to idle", function()
		assert.equals("status is not an object", model.parseStatus("bad").reason)
		assert.equals("unsupported status schema", model.parseStatus({ schema = 2, sessions = {} }).reason)
		assert.equals("sessions is not an array", model.parseStatus({ schema = 1 }).reason)
	end)

	it("rejects malformed active state and region fields", function()
		local malformed = {}
		for key, value in pairs(valid_active) do
			malformed[key] = value
		end
		malformed.state = "uploading"
		assert.equals(
			"invalid active recording",
			model.parseStatus({ schema = 1, active = malformed, sessions = {} }).reason
		)
		malformed.state = "recording"
		malformed.region = rect(0, 0, 0, 10)
		assert.equals(
			"invalid active recording",
			model.parseStatus({ schema = 1, active = malformed, sessions = {} }).reason
		)
	end)

	it("rejects malformed session entries and non-array keys", function()
		local invalid_session = { id = "x", name = "clip", status = "unknown" }
		local invalid = model.parseStatus({ schema = 1, active = nil, sessions = { invalid_session } })
		assert.equals("invalid session at index 1", invalid.reason)
		local invalid_array = { schema = 1, sessions = { named = true } }
		assert.equals("sessions is not an array", model.parseStatus(invalid_array).reason)
	end)

	it("validates session upload states, host results, and acknowledgement types", function()
		local session = status_session({
			id = "done",
			hosts = { apollo = "ok", athena = "pending" },
			acked = { notified = false, adopted = true },
		})
		local parsed = model.parseStatus({ schema = 1, sessions = { session } })
		assert.equals("idle", parsed.state)
		assert.equals(1, #parsed.sessions)
		session.hosts.apollo = "unknown"
		assert.equals("invalid session at index 1", model.parseStatus({ schema = 1, sessions = { session } }).reason)
		session.hosts.apollo = "ok"
		session.acked.notified = "false"
		assert.equals("invalid session at index 1", model.parseStatus({ schema = 1, sessions = { session } }).reason)
	end)
end)
