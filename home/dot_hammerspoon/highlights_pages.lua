-- Pure Highlights page-key state machine, jump runner, and alert copy (hs-free).
local M = {}

M.KEY_TIMEOUT_SECONDS = 1.0
M.MAX_COUNT_DIGITS = 6
M.MAX_JUMPS = 100
M.POLL_SECONDS = 0.05
M.LAND_TIMEOUT_SECONDS = 0.75
M.BUSY_MESSAGE = "Still jumping pages"

local function safe_can_arm(can_arm)
	local ok, result = pcall(can_arm)
	return ok and result == true
end

local function has_cmd_or_alt(key)
	return key.cmd == true or key.alt == true
end

local function key_plain(key)
	if type(key.plain) == "string" then
		return key.plain
	end
	return key.chars
end

local function idle_command(key)
	if key.autorepeat or has_cmd_or_alt(key) then
		return nil
	end
	if key.chars == "g" and not key.shift and not key.ctrl then
		return "pending_g"
	end
	if key.chars == "G" and key.ctrl ~= true then
		return { kind = "goto", target = "last" }
	end
	if not key.shift and not key.ctrl and type(key.chars) == "string" and key.chars:match("^[1-9]$") then
		return "count"
	end
	if key.ctrl and not key.shift and key_plain(key) == "o" then
		return { kind = "back" }
	end
	if key.ctrl and not key.shift and key_plain(key) == "i" then
		return { kind = "forward" }
	end
	return nil
end

--- Create the `gg` / `G` / count / Ctrl-O / Ctrl-I key state machine.
function M.new_keys(opts)
	opts = opts or {}
	local timeout = tonumber(opts.timeout) or M.KEY_TIMEOUT_SECONDS
	local self = { _state = "idle", _text = "", _last_at = 0 }

	function self:cancel()
		self._state = "idle"
		self._text = ""
	end

	function self:is_pending()
		return self._state ~= "idle"
	end

	local function arm(self, state, text, now)
		self._state = state
		self._text = text or ""
		self._last_at = now
		return { swallow = true }
	end

	local function handle_idle(self, key, now, can_arm)
		local action = idle_command(key)
		if action == nil then
			return { swallow = false }
		end
		if not safe_can_arm(can_arm) then
			return { swallow = false }
		end
		if action == "pending_g" then
			return arm(self, "g", "", now)
		elseif action == "count" then
			return arm(self, "count", key.chars, now)
		end
		return { swallow = true, command = action }
	end

	function self:on_key(key, now, can_arm)
		key = type(key) == "table" and key or {}
		now = tonumber(now) or 0
		can_arm = type(can_arm) == "function" and can_arm or function()
			return false
		end

		if self._state ~= "idle" and now - self._last_at > timeout then
			self:cancel()
			return handle_idle(self, key, now, can_arm)
		end
		if self._state == "idle" then
			return handle_idle(self, key, now, can_arm)
		end
		if key.autorepeat then
			return { swallow = true }
		end
		if key.escape then
			self:cancel()
			return { swallow = true }
		end

		local chord = has_cmd_or_alt(key) or (key.ctrl and key_plain(key) ~= "o")
		if chord then
			self:cancel()
			return handle_idle(self, key, now, can_arm)
		end

		if self._state == "g" then
			if key.chars == "g" and not key.shift and not key.ctrl then
				self:cancel()
				return { swallow = true, command = { kind = "goto", target = "first" } }
			end
			self:cancel()
			return handle_idle(self, key, now, can_arm)
		end

		if self._state == "count" then
			if type(key.chars) == "string" and key.chars:match("^%d$") then
				local next_text = self._text .. key.chars
				if #next_text > M.MAX_COUNT_DIGITS then
					self:cancel()
					return { swallow = true }
				end
				return arm(self, "count", next_text, now)
			end
			if (key.chars == "g" or key.chars == "G") and not key.ctrl then
				local target = tonumber(self._text)
				self:cancel()
				return { swallow = true, command = { kind = "goto", target = target } }
			end
			self:cancel()
			return handle_idle(self, key, now, can_arm)
		end
		self:cancel()
		return handle_idle(self, key, now, can_arm)
	end

	return self
end

--- Parse the physical page and page count from a Highlights window title.
function M.parse_title(title)
	if type(title) ~= "string" then
		return nil
	end
	local page, count = title:match("[%s%-%–%—]+[Pp][Aa][Gg][Ee]%s+(%d+)%s+[Oo][Ff]%s+(%d+)%s*$")
	page, count = tonumber(page), tonumber(count)
	if page == nil or count == nil or page < 1 or count < 1 or page > count then
		return nil
	end
	return page, count
end

--- Add a page to one document's bounded, duplicate-free jump stack.
function M.push_jump(jumps, document, page)
	if type(jumps) ~= "table" or type(document) ~= "string" or document == "" or type(page) ~= "number" then
		return false
	end
	local stack = jumps[document]
	if type(stack) ~= "table" then
		stack = {}
		jumps[document] = stack
	end
	if stack[#stack] == page then
		return false
	end
	stack[#stack + 1] = page
	while #stack > M.MAX_JUMPS do
		table.remove(stack, 1)
	end
	return true
end

--- Create an empty back/forward jump history (one stack per PDF per side).
function M.new_history()
	return { back = {}, forward = {} }
end

--- Pop the newest page not equal to the current page.
function M.pop_jump(jumps, document, current)
	if type(jumps) ~= "table" or type(document) ~= "string" then
		return nil
	end
	local stack = jumps[document]
	if type(stack) ~= "table" then
		return nil
	end
	while #stack > 0 and stack[#stack] == current do
		table.remove(stack)
	end
	return table.remove(stack)
end

local function call(fn, ...)
	if type(fn) ~= "function" then
		return false, nil, "missing dependency"
	end
	local ok, first, second = pcall(fn, ...)
	if not ok then
		return false, nil, tostring(first)
	end
	return true, first, second
end

local function read_page_info(deps)
	local ok, info, reason = call(deps.page_info)
	if not ok or type(info) ~= "table" then
		return nil, reason or (type(info) == "string" and info) or "couldn't read Highlights' page number"
	end
	if type(info.page) ~= "number" or type(info.count) ~= "number" or type(info.document) ~= "string" then
		return nil, "couldn't read Highlights' page number"
	end
	return info
end

local function safe_now(deps)
	local ok, value = call(deps.now)
	if ok and type(value) == "number" then
		return value
	end
	return os.clock()
end

--- Run a page jump, polling the title and geometry until one mechanism lands.
--- History holds a back stack and a forward stack per PDF. A command changes
--- history only once its jump lands (`done`), except a back/forward target is
--- popped up front and restored on failure.
function M.run(command, history, deps, on_done)
	command = type(command) == "table" and command or {}
	if type(history) ~= "table" then
		history = {}
	end
	if type(history.back) ~= "table" then
		history.back = {}
	end
	if type(history.forward) ~= "table" then
		history.forward = {}
	end
	deps = type(deps) == "table" and deps or {}
	on_done = type(on_done) == "function" and on_done or function() end
	local completed = false
	local function finish(result)
		if completed then
			return
		end
		completed = true
		pcall(on_done, result)
	end

	local info = read_page_info(deps)
	if info == nil then
		finish({ status = "failed", kind = command.kind, reason = "couldn't read Highlights' page number" })
		return
	end
	local target = command.target
	if command.kind == "goto" then
		if target == "first" then
			target = 1
		elseif target == "last" then
			target = info.count
		end
		if type(target) ~= "number" or target < 1 or target > info.count or target % 1 ~= 0 then
			finish({ status = "out_of_range", kind = "goto", page = target, count = info.count, from = info.page })
			return
		end
	elseif command.kind == "back" then
		target = M.pop_jump(history.back, info.document, info.page)
		if target == nil then
			finish({ status = "empty", kind = "back", page = nil, count = info.count, from = info.page })
			return
		end
	elseif command.kind == "forward" then
		target = M.pop_jump(history.forward, info.document, info.page)
		if target == nil then
			finish({ status = "empty", kind = "forward", page = nil, count = info.count, from = info.page })
			return
		end
	else
		finish({ status = "failed", kind = command.kind, reason = "unknown page command" })
		return
	end

	local function record_landed()
		if command.kind == "goto" then
			if target ~= info.page then
				M.push_jump(history.back, info.document, info.page)
				history.forward[info.document] = nil
			end
		elseif command.kind == "back" then
			M.push_jump(history.forward, info.document, info.page)
		elseif command.kind == "forward" then
			M.push_jump(history.back, info.document, info.page)
		end
	end

	local function failed(reason)
		if command.kind == "back" then
			M.push_jump(history.back, info.document, target)
		elseif command.kind == "forward" then
			M.push_jump(history.forward, info.document, target)
		end
		finish({
			status = "failed",
			kind = command.kind,
			page = target,
			count = info.count,
			from = info.page,
			reason = reason,
		})
	end

	local attempts = {
		{ name = "scroll_bar", fn = deps.scroll_to },
		{ name = "scroll_to_visible", fn = deps.scroll_to_visible },
	}
	local attempt_index = 0
	local started_count = 0
	local function attempt_next()
		attempt_index = attempt_index + 1
		local attempt = attempts[attempt_index]
		if attempt == nil then
			failed(started_count == 0 and "couldn't find the PDF view" or "didn't reach page " .. tostring(target))
			return
		end
		local ok, started = call(attempt.fn, target)
		if not ok or started ~= true then
			attempt_next()
			return
		end
		started_count = started_count + 1
		local deadline = safe_now(deps) + M.LAND_TIMEOUT_SECONDS
		local function poll()
			if completed then
				return
			end
			local current = read_page_info(deps)
			local landed_ok, landed = call(deps.landed, target)
			if (current ~= nil and current.page == target) or (landed_ok and landed == true) then
				if attempt.name == "scroll_to_visible" then
					call(deps.log, "Highlights page scroll-bar jump missed; AXScrollToVisible landed")
				end
				record_landed()
				finish({
					status = "done",
					kind = command.kind,
					page = target,
					count = info.count,
					from = info.page,
					via = attempt.name,
				})
				return
			end
			if safe_now(deps) >= deadline then
				attempt_next()
				return
			end
			local after_ok = call(deps.after, M.POLL_SECONDS, poll)
			if not after_ok then
				attempt_next()
			end
		end
		poll()
	end
	attempt_next()
end

--- One-line alert copy. Successful jumps deliberately return nil (quiet success).
function M.message(result)
	result = result or {}
	if result.status == "busy" then
		return M.BUSY_MESSAGE
	elseif result.status == "done" then
		return nil
	elseif result.status == "out_of_range" then
		local noun = result.count == 1 and "page" or "pages"
		return string.format("No page %s — this PDF has %s %s", tostring(result.page), tostring(result.count), noun)
	elseif result.status == "empty" then
		if result.kind == "forward" then
			return "No later page"
		end
		return "No earlier page"
	elseif result.status == "failed" then
		if result.reason == "couldn't read Highlights' page number" then
			return "Couldn't read Highlights' page number"
		end
		if result.kind == "back" then
			return string.format("Couldn't go back to page %s: %s", tostring(result.page), tostring(result.reason))
		end
		if result.kind == "forward" then
			return string.format("Couldn't go forward to page %s: %s", tostring(result.page), tostring(result.reason))
		end
		return string.format("Couldn't jump to page %s: %s", tostring(result.page), tostring(result.reason))
	end
	return nil
end

return M
