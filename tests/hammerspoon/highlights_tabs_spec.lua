local HIGHLIGHTS_TABS_PATH = "home/dot_hammerspoon/highlights_tabs.lua"

local function load_pure()
	local chunk = assert(loadfile(HIGHLIGHTS_TABS_PATH))
	return chunk()
end

local function make_leader(M, timeout)
	return M.new_leader({ timeout = timeout or M.LEADER_TIMEOUT_SECONDS })
end

local function bare_backslash()
	return { chars = "\\", escape = false, cmd = false, alt = false, ctrl = false, shift = false, autorepeat = false }
end

local function key_with(chars, overrides)
	overrides = overrides or {}
	return {
		chars = chars,
		escape = overrides.escape or false,
		cmd = overrides.cmd or false,
		alt = overrides.alt or false,
		ctrl = overrides.ctrl or false,
		shift = overrides.shift or false,
		autorepeat = overrides.autorepeat or false,
	}
end

describe("Highlights leader state machine", function()
	local M = nil

	before_each(function()
		M = load_pure()
		package.loaded.highlights_tabs = nil
	end)

	it("arms only on a bare backslash when can_arm is true", function()
		local leader = make_leader(M)
		local can_arm_calls = 0
		local function can_arm()
			can_arm_calls = can_arm_calls + 1
			return true
		end
		local result = leader:on_key(bare_backslash(), 100, can_arm)
		assert.is_true(result.swallow)
		assert.is_nil(result.command)
		assert.equals(1, can_arm_calls)
		assert.is_true(leader:is_pending())
	end)

	it("never calls can_arm for other keys", function()
		local leader = make_leader(M)
		local calls = 0
		local function can_arm()
			calls = calls + 1
			return true
		end
		local result = leader:on_key(key_with("j"), 100, can_arm)
		assert.is_false(result.swallow)
		assert.equals(0, calls)
		assert.is_false(leader:is_pending())
	end)

	it("does not arm when can_arm is false", function()
		local leader = make_leader(M)
		local result = leader:on_key(bare_backslash(), 100, function()
			return false
		end)
		assert.is_false(result.swallow)
		assert.is_false(leader:is_pending())
	end)

	it("fires others, left, and right", function()
		local leader = make_leader(M)
		leader:on_key(bare_backslash(), 100, function()
			return true
		end)
		local others = leader:on_key(key_with("\\"), 100.2, function()
			error("can_arm must be lazy")
		end)
		assert.is_true(others.swallow)
		assert.equals("others", others.command)
		assert.is_false(leader:is_pending())

		leader:on_key(bare_backslash(), 200, function()
			return true
		end)
		local left = leader:on_key(key_with("<", { shift = true }), 200.1, function()
			error("can_arm must be lazy")
		end)
		assert.equals("left", left.command)
		assert.is_true(left.swallow)

		leader:on_key(bare_backslash(), 300, function()
			return true
		end)
		local right = leader:on_key(key_with(">", { shift = true }), 300.1, function()
			error("can_arm must be lazy")
		end)
		assert.equals("right", right.command)
		assert.is_true(right.swallow)
	end)

	it("fires reopen on u", function()
		local leader = make_leader(M)
		leader:on_key(bare_backslash(), 100, function()
			return true
		end)
		local result = leader:on_key(key_with("u"), 100.2, function()
			return true
		end)
		assert.is_true(result.swallow)
		assert.equals("reopen", result.command)
		assert.is_false(leader:is_pending())
	end)

	it("escape cancels and is swallowed", function()
		local leader = make_leader(M)
		leader:on_key(bare_backslash(), 100, function()
			return true
		end)
		local result = leader:on_key(key_with(nil, { escape = true }), 100.1, function()
			return true
		end)
		assert.is_true(result.swallow)
		assert.is_nil(result.command)
		assert.is_false(leader:is_pending())
	end)

	it("another key cancels and passes through", function()
		local leader = make_leader(M)
		leader:on_key(bare_backslash(), 100, function()
			return true
		end)
		local result = leader:on_key(key_with("j"), 100.1, function()
			return true
		end)
		assert.is_false(result.swallow)
		assert.is_nil(result.command)
		assert.is_false(leader:is_pending())
	end)

	it("a cmd chord cancels and passes through", function()
		for _, mod in ipairs({ "cmd", "ctrl", "alt" }) do
			local leader = make_leader(M)
			leader:on_key(bare_backslash(), 100, function()
				return true
			end)
			local overrides = {}
			overrides[mod] = true
			local result = leader:on_key(key_with("u", overrides), 100.1, function()
				return true
			end)
			assert.is_false(result.swallow)
			assert.is_false(leader:is_pending())
		end
	end)

	it("an autorepeat while pending is swallowed and fires nothing", function()
		local leader = make_leader(M)
		leader:on_key(bare_backslash(), 100, function()
			return true
		end)
		local result = leader:on_key(key_with("\\", { autorepeat = true }), 100.1, function()
			return true
		end)
		assert.is_true(result.swallow)
		assert.is_nil(result.command)
		assert.is_true(leader:is_pending())
	end)

	it("an autorepeat backslash while idle does not arm", function()
		local leader = make_leader(M)
		local result = leader:on_key(key_with("\\", { autorepeat = true }), 100, function()
			return true
		end)
		assert.is_false(result.swallow)
		assert.is_false(leader:is_pending())
	end)

	it("expiry after 1 s makes the second backslash re-arm instead of firing", function()
		local leader = make_leader(M)
		leader:on_key(bare_backslash(), 100, function()
			return true
		end)
		local result = leader:on_key(bare_backslash(), 101.5, function()
			return true
		end)
		assert.is_true(result.swallow)
		assert.is_nil(result.command)
		assert.is_true(leader:is_pending())
	end)

	it("cancel works", function()
		local leader = make_leader(M)
		leader:on_key(bare_backslash(), 100, function()
			return true
		end)
		leader:cancel()
		assert.is_false(leader:is_pending())
	end)
end)

local function make_state(titles, selected)
	return {
		titles = titles,
		selected = selected,
		select_calls = 0,
		close_calls = 0,
		sheet = false,
		never_close = false,
		fail_select = false,
		no_group = false,
		unreadable = false,
		no_document = false,
	}
end

local function make_deps(M, state)
	local queue = {}
	local now = 1000
	local deps = {}
	deps.now = function()
		return now
	end
	deps.after = function(seconds, fn)
		table.insert(queue, { seconds = seconds, fn = fn })
	end
	deps.read = function()
		if state.unreadable then
			return nil, state.read_reason or "boom"
		end
		if state.no_group then
			return { tabs = nil }
		end
		local tabs = {}
		for index, title in ipairs(state.titles) do
			table.insert(tabs, { title = title, selected = index == state.selected })
		end
		return { tabs = tabs }
	end
	deps.select = function(index)
		state.select_calls = state.select_calls + 1
		if state.fail_select then
			return false
		end
		if type(index) ~= "number" or index < 1 or index > #state.titles then
			return false
		end
		state.selected = index
		return true
	end
	deps.close_selected = function()
		state.close_calls = state.close_calls + 1
		if state.never_close then
			return true
		end
		if state.selected < 1 or state.selected > #state.titles then
			return false
		end
		table.remove(state.titles, state.selected)
		if state.selected > #state.titles then
			state.selected = #state.titles
		end
		if state.vanish_when_one and #state.titles == 1 then
			state.no_group = true
		end
		return true
	end
	deps.has_sheet = function()
		return state.sheet == true
	end
	deps.document = function()
		if state.no_document then
			return nil
		end
		local title = state.titles[state.selected]
		if title == nil then
			return nil
		end
		return "/pdfs/" .. title
	end
	local function advance(seconds)
		now = now + (tonumber(seconds) or 0)
	end
	local function drain(limit)
		limit = limit or 500
		local ticks = 0
		while #queue > 0 and ticks < limit do
			ticks = ticks + 1
			local item = table.remove(queue, 1)
			advance(item.seconds)
			item.fn()
		end
		return ticks
	end
	return deps, queue, drain, state, function()
		return now
	end
end

local function run_and_drain(M, mode, state)
	local deps, queue, drain, kept = make_deps(M, state)
	local finished = nil
	M.run_close(mode, deps, function(result)
		finished = result
	end)
	drain()
	return finished, kept, queue
end

describe("Highlights close runner", function()
	local M = nil

	before_each(function()
		M = load_pure()
		package.loaded.highlights_tabs = nil
	end)

	it("closes right tabs to the right and reselects the kept tab", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf" }, 2)
		local finished = run_and_drain(M, "right", state)
		assert.equals("done", finished.status)
		assert.equals(3, finished.closed)
		assert.same({ "a.pdf", "b.pdf" }, state.titles)
		assert.equals(2, state.selected)
		assert.equals(3, state.close_calls)
		assert.equals(3, #finished.paths)
	end)

	it("closes left tabs leftmost-first", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf", "d.pdf" }, 3)
		local finished = run_and_drain(M, "left", state)
		assert.equals("done", finished.status)
		assert.equals(2, finished.closed)
		assert.same({ "c.pdf", "d.pdf" }, state.titles)
		assert.equals(1, state.selected)
	end)

	it("closes others and keeps the middle tab", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf" }, 2)
		local finished = run_and_drain(M, "others", state)
		assert.equals("done", finished.status)
		assert.equals(2, finished.closed)
		assert.same({ "b.pdf" }, state.titles)
	end)

	it("reports nothing for a single tab", function()
		local state = make_state({ "only.pdf" }, 1)
		local finished = run_and_drain(M, "others", state)
		assert.equals("nothing", finished.status)
		assert.equals(0, finished.closed)
		assert.equals(0, state.close_calls)
	end)

	it("reports nothing for a nil tab group", function()
		local state = make_state({ "a.pdf" }, 1)
		state.no_group = true
		local finished = run_and_drain(M, "right", state)
		assert.equals("nothing", finished.status)
		assert.equals(0, state.close_calls)
	end)

	it("reports nothing at the leftmost and rightmost edges", function()
		local left_edge = run_and_drain(M, "left", make_state({ "a.pdf", "b.pdf" }, 1))
		assert.equals("nothing", left_edge.status)
		local right_edge = run_and_drain(M, "right", make_state({ "a.pdf", "b.pdf" }, 2))
		assert.equals("nothing", right_edge.status)
	end)

	it("keeps duplicate titles safe by position", function()
		local state = make_state({ "dup.pdf", "dup.pdf", "keep.pdf" }, 3)
		local finished = run_and_drain(M, "left", state)
		assert.equals("done", finished.status)
		assert.equals(2, finished.closed)
		assert.same({ "keep.pdf" }, state.titles)
	end)

	it("fails on a select timeout without closing", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf" }, 2)
		state.fail_select = true
		local deps, _, drain, kept = make_deps(M, state)
		local finished = nil
		M.run_close("right", deps, function(result)
			finished = result
		end)
		drain()
		assert.equals("failed", finished.status)
		assert.equals(0, finished.closed)
		assert.equals(0, kept.close_calls)
	end)

	it("fails on a close timeout and never presses close twice for that tab", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf" }, 1)
		state.never_close = true
		local deps, _, drain, kept = make_deps(M, state)
		local finished = nil
		M.run_close("right", deps, function(result)
			finished = result
		end)
		drain()
		assert.equals("failed", finished.status)
		assert.equals(0, finished.closed)
		assert.equals(1, kept.close_calls)
	end)

	it("stops with needs_attention on a sheet and does not reselect", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf" }, 1)
		state.sheet = true
		local deps, _, drain, kept = make_deps(M, state)
		local finished = nil
		local reselects_before = kept.select_calls
		M.run_close("right", deps, function(result)
			finished = result
		end)
		drain()
		assert.equals("needs_attention", finished.status)
		assert.equals(0, finished.closed)
		-- One select for the target, no kept-tab reselect after the sheet.
		assert.equals(reselects_before + 1, kept.select_calls)
	end)

	it("fails when no tab is selected", function()
		local finished = run_and_drain(M, "right", make_state({ "a.pdf", "b.pdf" }, nil))
		assert.equals("failed", finished.status)
		assert.equals(0, finished.closed)
		assert.equals("couldn't tell which tab is selected", finished.reason)
	end)

	it("fails on drift", function()
		local M_local = M
		local deps, _, drain = make_deps(M_local, make_state({ "a.pdf", "b.pdf" }, 1))
		local calls = 0
		local real_read = deps.read
		deps.read = function()
			calls = calls + 1
			if calls >= 3 then
				return { tabs = { { title = "changed.pdf", selected = true }, { title = "b.pdf" } } }
			end
			return real_read()
		end
		local finished = nil
		M_local.run_close("right", deps, function(result)
			finished = result
		end)
		drain()
		assert.equals("failed", finished.status)
	end)

	it("treats the vanishing tab group after the last close as done", function()
		local state = make_state({ "a.pdf", "b.pdf" }, 1)
		state.vanish_when_one = true
		local finished = run_and_drain(M, "right", state)
		assert.equals("done", finished.status)
		assert.equals(1, finished.closed)
	end)

	it("caps iterations at the planned count", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf" }, 2)
		local finished = run_and_drain(M, "others", state)
		assert.equals("done", finished.status)
		assert.equals(4, finished.closed)
		assert.equals(4, state.close_calls)
		assert.same({ "b.pdf" }, state.titles)
	end)

	it("records document paths for reopen", function()
		local state = make_state({ "a.pdf", "b.pdf", "c.pdf" }, 2)
		local finished = run_and_drain(M, "left", state)
		assert.equals("done", finished.status)
		assert.equals(1, #finished.paths)
		assert.equals("/pdfs/a.pdf", finished.paths[1])
	end)
end)

describe("Highlights alert copy", function()
	local M = nil

	before_each(function()
		M = load_pure()
		package.loaded.highlights_tabs = nil
	end)

	it("covers done copy", function()
		assert.equals("Closed 1 tab to the right", M.message("right", { status = "done", closed = 1 }))
		assert.equals("Closed 3 tabs to the left", M.message("left", { status = "done", closed = 3 }))
		assert.equals("Closed 4 other tabs", M.message("others", { status = "done", closed = 4 }))
		assert.equals("Closed 1 other tab", M.message("others", { status = "done", closed = 1 }))
	end)

	it("covers nothing copy", function()
		assert.equals("No tabs to the left", M.message("left", { status = "nothing" }))
		assert.equals("No tabs to the right", M.message("right", { status = "nothing" }))
		assert.equals("No other tabs", M.message("others", { status = "nothing" }))
	end)

	it("covers needs_attention copy", function()
		assert.equals(
			"Highlights needs you — answer the save dialog (closed 2)",
			M.message("right", { status = "needs_attention", closed = 2 })
		)
	end)

	it("covers failed copy", function()
		assert.equals(
			"Stopped after closing 1 tab(s): boom",
			M.message("left", { status = "failed", closed = 1, reason = "boom" })
		)
	end)

	it("covers busy and reopen copy", function()
		assert.equals("Still closing Highlights tabs", M.message("busy", {}))
		assert.equals("Still closing Highlights tabs", M.BUSY_MESSAGE)
		assert.equals("Reopened 2 tabs", M.message("reopen", { status = "reopened", count = 2 }))
		assert.equals("Reopened 1 tab", M.message("reopen", { status = "reopened", count = 1 }))
		assert.equals("Nothing to reopen", M.message("reopen", { status = "empty" }))
	end)
end)
