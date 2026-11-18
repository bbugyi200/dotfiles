-- Pure Highlights tab-close leader model and close runner (hs-free).
-- The runtime module `highlights_tab_keys` requires this file and injects all
-- `hs` behaviour through `deps`, so busted can `loadfile` it directly.
local M = {}

M.BUNDLE_ID = "net.highlightsapp.universal"
M.LEADER_TIMEOUT_SECONDS = 1.0
M.POLL_SECONDS = 0.05
M.SELECT_TIMEOUT_SECONDS = 1.0
M.CLOSE_TIMEOUT_SECONDS = 2.0

M.BUSY_MESSAGE = "Still closing Highlights tabs"
M.CYCLE_CONFIRM_TIMEOUT_SECONDS = 0.5
M.CYCLE_MENU_PATHS = { [1] = { "Window", "Show Next Tab" }, [-1] = { "Window", "Show Previous Tab" } }

local function is_bare_backslash(key)
	return type(key) == "table"
		and key.chars == "\\"
		and not key.cmd
		and not key.alt
		and not key.ctrl
		and not key.shift
		and not key.autorepeat
end

local function has_any_cmd(key)
	return key.cmd == true or key.alt == true or key.ctrl == true
end

--- Create a `\` leader state machine.
--- `opts.timeout` defaults to `M.LEADER_TIMEOUT_SECONDS`.
function M.new_leader(opts)
	opts = opts or {}
	local timeout = tonumber(opts.timeout) or M.LEADER_TIMEOUT_SECONDS
	local self = {
		_pending = false,
		_armed_at = 0,
	}

	function self:cancel()
		self._pending = false
	end

	function self:is_pending()
		return self._pending
	end

	--- Handle one keyDown. `can_arm` is called lazily, only for a bare `\`.
	--- Returns `{ swallow = bool, command = nil | "others" | "left" | "right" | "reopen" }`.
	function self:on_key(key, now, can_arm)
		now = tonumber(now) or 0
		key = key or {}

		if self._pending and (now - self._armed_at > timeout) then
			self._pending = false
			return self:on_key(key, now, can_arm)
		end

		if not self._pending then
			if is_bare_backslash(key) then
				local ok, armed = pcall(can_arm)
				if ok and armed then
					self._pending = true
					self._armed_at = now
					return { swallow = true, command = nil }
				end
			end
			return { swallow = false, command = nil }
		end

		-- Pending.
		if key.autorepeat then
			return { swallow = true, command = nil }
		end
		if has_any_cmd(key) then
			self._pending = false
			return { swallow = false, command = nil }
		end
		if key.escape then
			self._pending = false
			return { swallow = true, command = nil }
		end
		local chars = key.chars
		if chars == "\\" and not key.shift then
			self._pending = false
			return { swallow = true, command = "others" }
		end
		if chars == "<" then
			self._pending = false
			return { swallow = true, command = "left" }
		end
		if chars == ">" then
			self._pending = false
			return { swallow = true, command = "right" }
		end
		if chars == "u" and not key.shift then
			self._pending = false
			return { swallow = true, command = "reopen" }
		end
		self._pending = false
		return { swallow = false, command = nil }
	end

	return self
end

local function plural_tabs(count)
	if count == 1 then
		return "1 tab"
	end
	return string.format("%d tabs", count)
end

--- One-line `hs.alert` copy for a finished run.
--- `mode` is "others" | "left" | "right" | "reopen" | "busy".
function M.message(mode, result)
	result = result or {}
	if mode == "busy" then
		return M.BUSY_MESSAGE
	end
	if mode == "reopen" then
		local status = result.status
		if status == "reopened" or status == "done" then
			local count = tonumber(result.count) or tonumber(result.closed) or 0
			return "Reopened " .. plural_tabs(count)
		end
		return "Nothing to reopen"
	end

	local status = result.status
	local closed = tonumber(result.closed) or 0
	if status == "done" then
		if mode == "left" then
			return "Closed " .. plural_tabs(closed) .. " to the left"
		elseif mode == "right" then
			return "Closed " .. plural_tabs(closed) .. " to the right"
		else
			if closed == 1 then
				return "Closed 1 other tab"
			end
			return string.format("Closed %d other tabs", closed)
		end
	elseif status == "nothing" then
		if mode == "left" then
			return "No tabs to the left"
		elseif mode == "right" then
			return "No tabs to the right"
		else
			return "No other tabs"
		end
	elseif status == "needs_attention" then
		return string.format("Highlights needs you — answer the save dialog (closed %d)", closed)
	elseif status == "failed" then
		return string.format("Stopped after closing %d tab(s): %s", closed, tostring(result.reason or "unknown"))
	else
		return string.format("Stopped after closing %d tab(s): %s", closed, tostring(result.reason or "unknown"))
	end
end

local function safe_read(deps)
	local ok, res, err = pcall(deps.read)
	if not ok then
		return nil, tostring(res or "unknown")
	end
	if res == nil then
		return nil, tostring(err or "couldn't read Highlights' tabs")
	end
	return res, nil
end

local function safe_call(fn, ...)
	if type(fn) ~= "function" then
		return false
	end
	local ok, res = pcall(fn, ...)
	if not ok then
		return false
	end
	return res
end

local function tab_count(snapshot)
	if type(snapshot) ~= "table" then
		return nil, "couldn't read Highlights' tabs"
	end
	if snapshot.tabs == nil then
		return 1, nil
	end
	if type(snapshot.tabs) ~= "table" then
		return nil, "couldn't read Highlights' tabs"
	end
	return #snapshot.tabs, nil
end

--- Close other/left/right tabs asynchronously via injected `deps`.
--- `deps` is `{ read, select, close_selected, has_sheet, after, now, document? }`.
--- `on_done` receives `{ status, closed, reason?, paths? }`.
function M.run_close(mode, deps, on_done)
	local function finish_once(result)
		local called = false
		return function(value)
			if called then
				return
			end
			called = true
			on_done(value)
		end
	end
	local done = finish_once()

	local valid_mode = mode == "others" or mode == "left" or mode == "right"
	if not valid_mode then
		done({ status = "failed", closed = 0, reason = "unknown close mode", paths = {} })
		return
	end
	if
		type(deps) ~= "table"
		or type(deps.read) ~= "function"
		or type(deps.select) ~= "function"
		or type(deps.close_selected) ~= "function"
		or type(deps.has_sheet) ~= "function"
		or type(deps.after) ~= "function"
		or type(deps.now) ~= "function"
	then
		done({ status = "failed", closed = 0, reason = "couldn't read Highlights' tabs", paths = {} })
		return
	end

	local initial, initial_err = safe_read(deps)
	if initial == nil then
		done({ status = "failed", closed = 0, reason = initial_err, paths = {} })
		return
	end
	if initial.tabs == nil then
		done({ status = "nothing", closed = 0, paths = {} })
		return
	end
	if type(initial.tabs) ~= "table" or #initial.tabs < 2 then
		done({ status = "nothing", closed = 0, paths = {} })
		return
	end

	local selected_index = nil
	for index, tab in ipairs(initial.tabs) do
		if type(tab) == "table" and tab.selected then
			selected_index = index
			break
		end
	end
	if selected_index == nil then
		done({ status = "failed", closed = 0, reason = "couldn't tell which tab is selected", paths = {} })
		return
	end

	local kept_title = nil
	if type(initial.tabs[selected_index]) == "table" then
		kept_title = initial.tabs[selected_index].title
	end
	local total = #initial.tabs
	local left_remaining = 0
	local right_remaining = 0
	if mode == "left" or mode == "others" then
		left_remaining = selected_index - 1
	end
	if mode == "right" or mode == "others" then
		right_remaining = total - selected_index
	end
	if left_remaining <= 0 and right_remaining <= 0 then
		done({ status = "nothing", closed = 0, paths = {} })
		return
	end

	local state = {
		kept_index = selected_index,
		kept_title = kept_title,
		left_remaining = left_remaining,
		right_remaining = right_remaining,
		closed = 0,
		paths = {},
		planned = left_remaining + right_remaining,
		steps = 0,
	}

	local function fail(reason)
		done({ status = "failed", closed = state.closed, reason = reason, paths = state.paths })
	end

	local function needs_attention()
		done({ status = "needs_attention", closed = state.closed, paths = state.paths })
	end

	local function finish_success()
		local ok, current = pcall(deps.read)
		if ok and type(current) == "table" and type(current.tabs) == "table" then
			local kept = current.tabs[state.kept_index]
			if
				type(kept) == "table"
				and kept.title == state.kept_title
				and not kept.selected
				and state.kept_index >= 1
				and state.kept_index <= #current.tabs
			then
				pcall(deps.select, state.kept_index)
			end
		end
		done({ status = "done", closed = state.closed, paths = state.paths })
	end

	local step
	local poll_select
	local poll_close

	step = function()
		if state.left_remaining <= 0 and state.right_remaining <= 0 then
			finish_success()
			return
		end
		state.steps = state.steps + 1
		if state.steps > state.planned then
			fail("tabs changed while closing")
			return
		end

		local current, read_err = safe_read(deps)
		if current == nil then
			fail(read_err)
			return
		end
		if current.tabs == nil then
			fail("tabs changed while closing")
			return
		end
		if type(current.tabs) ~= "table" then
			fail("couldn't read Highlights' tabs")
			return
		end
		local kept = current.tabs[state.kept_index]
		if type(kept) ~= "table" or kept.title ~= state.kept_title then
			fail("tabs changed while closing")
			return
		end

		local target = nil
		if state.left_remaining > 0 then
			target = 1
		else
			target = state.kept_index + 1
		end
		if type(current.tabs[target]) ~= "table" then
			fail("tabs changed while closing")
			return
		end

		local count_before = #current.tabs
		if current.tabs[target].selected then
			poll_close(target, count_before)
		else
			pcall(deps.select, target)
			local deadline = deps.now() + M.SELECT_TIMEOUT_SECONDS
			local function tick()
				local fresh, fresh_err = safe_read(deps)
				if fresh == nil then
					fail(fresh_err)
					return
				end
				if type(fresh.tabs) ~= "table" then
					fail("tabs changed while closing")
					return
				end
				local candidate = fresh.tabs[target]
				if type(candidate) == "table" and candidate.selected then
					poll_close(target, #fresh.tabs)
					return
				end
				if deps.now() >= deadline then
					fail("didn't switch to that tab")
					return
				end
				deps.after(M.POLL_SECONDS, tick)
			end
			deps.after(M.POLL_SECONDS, tick)
		end
	end

	poll_select = function()
		-- Reserved for future select-phase reuse; selection polls inline in step.
	end

	poll_close = function(target, count_before)
		-- Record the visible tab's document before closing so `\u` can reopen it.
		if type(deps.document) == "function" then
			local ok, path = pcall(deps.document)
			if ok and type(path) == "string" and path ~= "" then
				table.insert(state.paths, path)
			end
		end
		pcall(deps.close_selected)

		local deadline = deps.now() + M.CLOSE_TIMEOUT_SECONDS
		local function tick()
			if safe_call(deps.has_sheet) then
				needs_attention()
				return
			end
			local fresh, fresh_err = safe_read(deps)
			if fresh == nil then
				fail(fresh_err)
				return
			end
			local after_count, count_err = tab_count(fresh)
			if after_count == nil then
				fail(count_err)
				return
			end
			if after_count == count_before - 1 then
				state.closed = state.closed + 1
				if target == 1 then
					state.left_remaining = state.left_remaining - 1
					state.kept_index = state.kept_index - 1
				else
					state.right_remaining = state.right_remaining - 1
				end
				step()
				return
			end
			if safe_call(deps.has_sheet) then
				needs_attention()
				return
			end
			if deps.now() >= deadline then
				fail("didn't close that tab")
				return
			end
			deps.after(M.POLL_SECONDS, tick)
		end
		deps.after(M.POLL_SECONDS, tick)
	end

	-- Silence unused-function lint without changing behaviour.
	_ = poll_select

	step()
end

--- Tab-cycle helpers. `key.tab` is a keycode match set by the runtime, never
--- characters, because ⌃I and ⌃⇥ both produce `"\t"`.
function M.cycle_step(key)
	if type(key) ~= "table" then
		return nil
	end
	if key.tab ~= true then
		return nil
	end
	if key.ctrl ~= true then
		return nil
	end
	if key.cmd == true or key.alt == true then
		return nil
	end
	if key.shift == true then
		return -1
	end
	return 1
end

--- 1-based wraparound target for `steps` signed moves from `selected`.
function M.cycle_target(count, selected, steps)
	if type(count) ~= "number" or type(selected) ~= "number" or type(steps) ~= "number" then
		return nil
	end
	if count < 1 or count % 1 ~= 0 then
		return nil
	end
	if selected < 1 or selected > count or selected % 1 ~= 0 then
		return nil
	end
	if steps % 1 ~= 0 then
		return nil
	end
	return ((selected - 1 + steps) % count) + 1
end

--- Alert copy for a finished cycle batch.
function M.cycle_message(result)
	if type(result) ~= "table" then
		return nil
	end
	if result.status == "failed" then
		return "Couldn't switch Highlights tabs: " .. tostring(result.reason or "unknown")
	end
	return nil
end

--- Serialized, coalescing tab-cycle runner.
--- `deps` is `{ read, select, menu_step(direction) -> bool, after, now }`.
--- `on_result` receives `{ status, reason?, fresh }` after each batch.
function M.new_cycler(deps, on_result)
	deps = type(deps) == "table" and deps or {}
	local handle_result = type(on_result) == "function" and on_result or function() end
	local self = {
		_pending_steps = 0,
		_pending_fresh = false,
		_in_flight = false,
		_scheduled = false,
		_idle_q = {},
	}

	local function safe_after(seconds, fn)
		if type(deps.after) ~= "function" then
			return nil
		end
		local ok, timer = pcall(deps.after, seconds, fn)
		if not ok then
			return nil
		end
		return timer
	end

	local function safe_now()
		if type(deps.now) == "function" then
			local ok, value = pcall(deps.now)
			if ok and type(value) == "number" then
				return value
			end
		end
		return os.clock()
	end

	local function safe_read()
		if type(deps.read) ~= "function" then
			return nil, "couldn't read Highlights' tabs"
		end
		local ok, res, err = pcall(deps.read)
		if not ok then
			return nil, tostring(res or "unknown")
		end
		if res == nil then
			return nil, tostring(err or "couldn't read Highlights' tabs")
		end
		return res, nil
	end

	local function safe_select(index)
		if type(deps.select) ~= "function" then
			return false
		end
		local ok, res = pcall(deps.select, index)
		if not ok then
			return false
		end
		return res
	end

	local function safe_menu(direction)
		if type(deps.menu_step) ~= "function" then
			return false
		end
		local ok, res = pcall(deps.menu_step, direction)
		if not ok then
			return false
		end
		return res
	end

	local run_batch
	local function complete_batch(result)
		pcall(handle_result, result)
		if self._pending_steps ~= 0 then
			local steps = self._pending_steps
			local fresh = self._pending_fresh
			self._pending_steps = 0
			self._pending_fresh = false
			run_batch(steps, fresh)
		else
			self._in_flight = false
			local queued = self._idle_q
			self._idle_q = {}
			for _, fn in ipairs(queued) do
				pcall(fn)
			end
		end
	end

	run_batch = function(steps, fresh)
		local snapshot, read_err = safe_read()
		if snapshot == nil then
			complete_batch({ status = "failed", reason = read_err, fresh = fresh })
			return
		end
		if snapshot.tabs == nil then
			local sign = 0
			if steps > 0 then
				sign = 1
			elseif steps < 0 then
				sign = -1
			end
			local any_ok = false
			if sign ~= 0 then
				for _ = 1, math.abs(steps) do
					if safe_menu(sign) then
						any_ok = true
					end
				end
			end
			if any_ok then
				complete_batch({ status = "done", fresh = fresh })
			else
				complete_batch({ status = "nothing", fresh = fresh })
			end
			return
		end
		if type(snapshot.tabs) ~= "table" then
			complete_batch({ status = "failed", reason = "couldn't read Highlights' tabs", fresh = fresh })
			return
		end
		local count = #snapshot.tabs
		local selected = nil
		for index, tab in ipairs(snapshot.tabs) do
			if type(tab) == "table" and tab.selected then
				selected = index
				break
			end
		end
		if selected == nil then
			complete_batch({ status = "failed", reason = "couldn't tell which tab is selected", fresh = fresh })
			return
		end
		local target = M.cycle_target(count, selected, steps)
		if target == nil then
			complete_batch({ status = "failed", reason = "couldn't read Highlights' tabs", fresh = fresh })
			return
		end
		if target == selected then
			complete_batch({ status = "done", fresh = fresh })
			return
		end
		safe_select(target)
		local deadline = safe_now() + M.CYCLE_CONFIRM_TIMEOUT_SECONDS
		local function poll()
			local fresh_snapshot, fresh_err = safe_read()
			if fresh_snapshot == nil then
				complete_batch({ status = "failed", reason = fresh_err, fresh = fresh })
				return
			end
			if type(fresh_snapshot.tabs) == "table" then
				local candidate = fresh_snapshot.tabs[target]
				if type(candidate) == "table" and candidate.selected then
					complete_batch({ status = "done", fresh = fresh })
					return
				end
			end
			if safe_now() >= deadline then
				self._pending_steps = 0
				self._pending_fresh = false
				complete_batch({ status = "failed", reason = "didn't switch to that tab", fresh = fresh })
				return
			end
			safe_after(M.POLL_SECONDS, poll)
		end
		safe_after(M.POLL_SECONDS, poll)
	end

	local function flush()
		if self._in_flight then
			return
		end
		if self._pending_steps == 0 then
			self._scheduled = false
			return
		end
		local steps = self._pending_steps
		local fresh = self._pending_fresh
		self._pending_steps = 0
		self._pending_fresh = false
		self._scheduled = false
		self._in_flight = true
		run_batch(steps, fresh)
	end

	function self:push(step, fresh)
		if type(step) ~= "number" or step % 1 ~= 0 then
			return
		end
		self._pending_steps = self._pending_steps + step
		if fresh then
			self._pending_fresh = true
		end
		if not self._in_flight and not self._scheduled then
			self._scheduled = true
			safe_after(0, flush)
		end
	end

	function self:is_busy()
		return self._in_flight == true or self._pending_steps ~= 0
	end

	function self:when_idle(fn)
		if type(fn) ~= "function" then
			return
		end
		if not self:is_busy() then
			pcall(fn)
		else
			table.insert(self._idle_q, fn)
		end
	end

	function self:cancel()
		self._pending_steps = 0
		self._pending_fresh = false
	end

	return self
end

return M
