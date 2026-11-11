local HIGHLIGHTS_PAGES_PATH = "home/dot_hammerspoon/highlights_pages.lua"

local function load_pure()
	return assert(loadfile(HIGHLIGHTS_PAGES_PATH))()
end

local function key(chars, overrides)
	local result = {
		chars = chars,
		plain = chars,
		escape = false,
		cmd = false,
		alt = false,
		ctrl = false,
		shift = false,
		autorepeat = false,
	}
	for name, value in pairs(overrides or {}) do
		result[name] = value
	end
	return result
end

local function run_fake(M, command, state, overrides)
	overrides = overrides or {}
	local env = {
		now = 0,
		queue = {},
		logs = {},
		calls = { scroll_to = 0, scroll_to_visible = 0 },
	}
	local deps = {
		page_info = overrides.page_info or function()
			if state.read_error then
				return nil, state.read_error
			end
			return { page = state.page, count = state.count, document = state.document or "/paper.pdf" }
		end,
		scroll_to = overrides.scroll_to or function(page)
			env.calls.scroll_to = env.calls.scroll_to + 1
			if overrides.primary_lands ~= false then
				state.page = page
			end
			return overrides.primary_result ~= false
		end,
		scroll_to_visible = overrides.scroll_to_visible or function(page)
			env.calls.scroll_to_visible = env.calls.scroll_to_visible + 1
			if overrides.fallback_lands == true then
				state.page = page
			end
			return overrides.fallback_result ~= false
		end,
		landed = overrides.landed or function(page)
			return state.page == page
		end,
		after = function(seconds, fn)
			table.insert(env.queue, { seconds = seconds, fn = fn })
		end,
		now = function()
			return env.now
		end,
		log = function(message)
			table.insert(env.logs, message)
		end,
	}
	local result = nil
	if type(state.history) ~= "table" then
		state.history = M.new_history()
	end
	M.run(command, state.history, deps, function(value)
		result = value
	end)
	local steps = 0
	while #env.queue > 0 and steps < 100 do
		steps = steps + 1
		local queued = table.remove(env.queue, 1)
		env.now = env.now + queued.seconds
		queued.fn()
	end
	assert.is_true(steps < 100, "runner queue should drain")
	return result, env
end

describe("Highlights page keys", function()
	local M = nil

	before_each(function()
		M = load_pure()
	end)

	describe("key state machine", function()
		it("recognizes gg, G, and counted g/G jumps", function()
			local cases = {
				{ { key("g"), key("g") }, { kind = "goto", target = "first" } },
				{ { key("G", { shift = true }) }, { kind = "goto", target = "last" } },
				{ { key("2"), key("g") }, { kind = "goto", target = 2 } },
				{ { key("1"), key("2"), key("g") }, { kind = "goto", target = 12 } },
				{ { key("1"), key("2"), key("G", { shift = true }) }, { kind = "goto", target = 12 } },
				{ { key("1"), key("0"), key("g") }, { kind = "goto", target = 10 } },
			}
			for _, case in ipairs(cases) do
				local keys = M.new_keys()
				local outcome = nil
				for _, pressed in ipairs(case[1]) do
					outcome = keys:on_key(pressed, 10, function()
						return true
					end)
				end
				assert.same(case[2], outcome.command)
				assert.is_true(outcome.swallow)
				assert.is_false(keys:is_pending())
			end
		end)

		it("passes a bare zero and starts a count after g", function()
			local keys = M.new_keys()
			assert.is_false(keys:on_key(key("0"), 0, function()
				return true
			end).swallow)
			assert.is_true(keys:on_key(key("g"), 1, function()
				return true
			end).swallow)
			local count = keys:on_key(key("5"), 1.1, function()
				return true
			end)
			assert.is_true(count.swallow)
			assert.is_true(keys:is_pending())
			local command = keys:on_key(key("g"), 1.2, function()
				return true
			end)
			assert.same({ kind = "goto", target = 5 }, command.command)
		end)

		it("cancels on Escape and swallows autorepeat only while pending", function()
			local keys = M.new_keys()
			assert.is_false(keys:on_key(key("g", { autorepeat = true }), 0, function()
				return true
			end).swallow)
			keys:on_key(key("g"), 1, function()
				return true
			end)
			assert.is_true(keys:on_key(key("g", { autorepeat = true }), 1.1).swallow)
			assert.is_true(keys:is_pending())
			local escaped = keys:on_key(key("escape", { escape = true }), 1.2)
			assert.is_true(escaped.swallow)
			assert.is_false(keys:is_pending())
		end)

		it("expires from the last swallowed key and rehandles the new key as idle", function()
			local keys = M.new_keys()
			keys:on_key(key("g"), 10, function()
				return true
			end)
			local result = keys:on_key(key("g"), 11.01, function()
				return true
			end)
			assert.is_true(result.swallow)
			assert.is_nil(result.command)
			assert.is_true(keys:is_pending())
		end)

		it("cancels command and option chords, passing them through", function()
			for _, chord in ipairs({ key("x", { cmd = true }), key("x", { alt = true }) }) do
				local keys = M.new_keys()
				keys:on_key(key("g"), 1, function()
					return true
				end)
				local result = keys:on_key(chord, 1.1, function()
					return true
				end)
				assert.is_false(result.swallow)
				assert.is_false(keys:is_pending())
			end
		end)

		it("cancels a count after a seventh digit", function()
			local keys = M.new_keys()
			for index = 1, 7 do
				local result = keys:on_key(key(tostring(index)), index, function()
					return true
				end)
				assert.is_true(result.swallow)
			end
			assert.is_false(keys:is_pending())
		end)

		it("fires Ctrl-O from idle and leaves shifted Ctrl-O alone", function()
			local keys = M.new_keys()
			local result = keys:on_key(key("\15", { plain = "o", ctrl = true }), 1, function()
				return true
			end)
			assert.is_true(result.swallow)
			assert.same({ kind = "back" }, result.command)
			assert.is_false(keys:on_key(key("\15", { plain = "o", ctrl = true, shift = true }), 2, function()
				return true
			end).swallow)
		end)

		it("fires Ctrl-I from idle and leaves modified Ctrl-I alone", function()
			local keys = M.new_keys()
			local result = keys:on_key(key("\9", { plain = "i", ctrl = true }), 1, function()
				return true
			end)
			assert.is_true(result.swallow)
			assert.same({ kind = "forward" }, result.command)
			for _, overrides in ipairs({
				{ plain = "i", ctrl = true, shift = true },
				{ plain = "i", ctrl = true, cmd = true },
				{ plain = "i", ctrl = true, alt = true },
				{ plain = "i", ctrl = true, autorepeat = true },
			}) do
				local other = M.new_keys()
				assert.is_false(other:on_key(key("\9", overrides), 2, function()
					return true
				end).swallow)
			end
		end)

		it("recognizes half-page and one-line scroll chords", function()
			local cases = {
				{ "d", "down", "half" },
				{ "u", "up", "half" },
				{ "e", "down", "line" },
				{ "y", "up", "line" },
			}
			for _, case in ipairs(cases) do
				local letter = case[1]
				local result = M.new_keys():on_key(
					key(string.char(letter:byte() - 96), { plain = letter, ctrl = true }),
					1,
					function()
						return true
					end
				)
				assert.is_true(result.swallow)
				assert.same({
					kind = "scroll",
					direction = case[2],
					amount = case[3],
					autorepeat = false,
				}, result.command)
			end
		end)

		it("accepts autorepeat only for scroll chords", function()
			local scroll = M.new_keys():on_key(key("\4", { plain = "d", ctrl = true, autorepeat = true }), 1, function()
				return true
			end)
			assert.is_true(scroll.swallow)
			assert.is_true(scroll.command.autorepeat)
			for _, repeated in ipairs({
				key("g", { autorepeat = true }),
				key("G", { shift = true, autorepeat = true }),
				key("\15", { plain = "o", ctrl = true, autorepeat = true }),
				key("5", { autorepeat = true }),
			}) do
				assert.is_false(M.new_keys():on_key(repeated, 1, function()
					return true
				end).swallow)
			end
		end)

		it("passes modified scroll chords and scrolls when can_arm allows it", function()
			for _, overrides in ipairs({
				{ plain = "d", ctrl = true, shift = true },
				{ plain = "d", ctrl = true, cmd = true },
				{ plain = "d", ctrl = true, alt = true },
			}) do
				assert.is_false(M.new_keys():on_key(key("\4", overrides), 1, function()
					return true
				end).swallow)
			end
			assert.is_false(M.new_keys():on_key(key("\4", { plain = "d", ctrl = true }), 1, function()
				return false
			end).swallow)
		end)

		it("cancels pending prefixes and counts before scrolling", function()
			local keys = M.new_keys()
			keys:on_key(key("g"), 1, function()
				return true
			end)
			local scroll = keys:on_key(key("\4", { plain = "d", ctrl = true }), 1.1, function()
				return true
			end)
			assert.same({ kind = "scroll", direction = "down", amount = "half", autorepeat = false }, scroll.command)
			local lone_g = keys:on_key(key("g"), 1.2, function()
				return true
			end)
			assert.is_nil(lone_g.command)
			assert.is_true(keys:is_pending())

			keys = M.new_keys()
			keys:on_key(key("5"), 2, function()
				return true
			end)
			local counted_scroll = keys:on_key(key("\5", { plain = "e", ctrl = true }), 2.1, function()
				return true
			end)
			assert.same(
				{ kind = "scroll", direction = "down", amount = "line", autorepeat = false },
				counted_scroll.command
			)
			assert.is_false(keys:is_pending())
		end)

		it("passes Tab and Ctrl-Tab through without calling can_arm", function()
			for _, overrides in ipairs({
				{ plain = "\t", chars = "\t" },
				{ plain = "\t", chars = "\t", ctrl = true },
			}) do
				local keys = M.new_keys()
				local calls = 0
				local result = keys:on_key(key("\t", overrides), 1, function()
					calls = calls + 1
					return true
				end)
				assert.is_false(result.swallow)
				assert.is_false(keys:is_pending())
				assert.equals(0, calls)
			end
		end)

		it("cancels a pending sequence on Ctrl-I and fires forward", function()
			local keys = M.new_keys()
			keys:on_key(key("g"), 1, function()
				return true
			end)
			assert.is_true(keys:is_pending())
			local fired = keys:on_key(key("\9", { plain = "i", ctrl = true }), 1.1, function()
				return true
			end)
			assert.is_true(fired.swallow)
			assert.same({ kind = "forward" }, fired.command)
			assert.is_false(keys:is_pending())

			keys = M.new_keys()
			keys:on_key(key("1"), 2, function()
				return true
			end)
			keys:on_key(key("2"), 2.1, function()
				return true
			end)
			assert.is_true(keys:is_pending())
			fired = keys:on_key(key("\9", { plain = "i", ctrl = true }), 2.2, function()
				return true
			end)
			assert.is_true(fired.swallow)
			assert.same({ kind = "forward" }, fired.command)
			assert.is_false(keys:is_pending())
		end)

		it("passes Ctrl-I when can_arm is false or throws", function()
			for _, can_arm in ipairs({
				function()
					return false
				end,
				function()
					error("AX failed")
				end,
			}) do
				local keys = M.new_keys()
				assert.is_false(keys:on_key(key("\9", { plain = "i", ctrl = true }), 1, can_arm).swallow)
				assert.is_false(keys:is_pending())
			end
		end)

		it("passes arming keys when can_arm is false or throws", function()
			for _, can_arm in ipairs({
				function()
					return false
				end,
				function()
					error("AX failed")
				end,
			}) do
				local keys = M.new_keys()
				assert.is_false(keys:on_key(key("g"), 1, can_arm).swallow)
				assert.is_false(keys:is_pending())
			end
		end)

		it("calls can_arm only for arming keys", function()
			local keys = M.new_keys()
			local calls = 0
			local function can_arm()
				calls = calls + 1
				return true
			end
			keys:on_key(key("x"), 1, can_arm)
			keys:on_key(key("0"), 2, can_arm)
			keys:on_key(key("G", { ctrl = true }), 3, can_arm)
			assert.equals(0, calls)
			keys:on_key(key("g"), 4, can_arm)
			assert.equals(1, calls)
		end)
	end)

	describe("title parser", function()
		it("accepts en, hyphen, and em dash separators with mixed case", function()
			for _, title in ipairs({
				"paper.pdf – Page 10 of 44",
				"paper.pdf - page 2 of 3",
				"paper.pdf — pAgE 1 Of 1",
			}) do
				local page, count = M.parse_title(title)
				assert.is_not_nil(page)
				assert.is_not_nil(count)
			end
		end)

		it("rejects missing separators, impossible pages, and empty titles", function()
			for _, title in ipairs({ "Page 3 of 5.pdf", "paper.pdf – Page 6 of 5", "", nil }) do
				assert.is_nil(M.parse_title(title))
			end
		end)
	end)

	describe("page URL requests", function()
		it("accepts an absolute PDF path and a bounded decimal page", function()
			assert.same(
				{ path = "/papers/a b.PDF", page = 999999 },
				M.parse_page_request({
					path = "/papers/a b.PDF",
					page = "999999",
				})
			)
		end)

		it("rejects missing, relative, non-PDF, NUL, and malformed page parameters", function()
			local missing, missing_reason = M.parse_page_request(nil)
			assert.is_nil(missing)
			assert.is_string(missing_reason)
			for _, params in ipairs({
				{},
				{ path = "paper.pdf", page = "1" },
				{ path = "/papers/paper.txt", page = "1" },
				{ path = "/papers/paper.pdf\0bad", page = "1" },
				{ path = "/papers/paper.pdf" },
				{ path = "/papers/paper.pdf", page = "0" },
				{ path = "/papers/paper.pdf", page = "4a" },
				{ path = "/papers/paper.pdf", page = "1000000" },
				{ path = "/papers/paper.pdf", page = 4 },
			}) do
				local request, reason = M.parse_page_request(params)
				assert.is_nil(request)
				assert.is_string(reason)
			end
		end)

		it("matches device and inode, and falls back to decoded path strings", function()
			local ids = {
				["/real/paper.pdf"] = { dev = 3, ino = 9 },
				["/alias/paper.pdf"] = { dev = 3, ino = 9 },
				["/other/paper.pdf"] = { dev = 3, ino = 10 },
			}
			local attributes = function(path)
				return ids[path]
			end
			assert.is_true(M.same_file("/real/paper.pdf", "/alias/paper.pdf", attributes))
			assert.is_false(M.same_file("/real/paper.pdf", "/other/paper.pdf", attributes))
			assert.is_true(M.same_file("/real/paper.pdf", "/real/paper.pdf", function()
				return nil
			end))
			assert.is_false(M.same_file("/real/paper.pdf", "/other/paper.pdf", function()
				error("unavailable")
			end))
		end)

		it("waits for a matching settled PDF and cancels only after it leaves the front", function()
			local state = {}
			local status = M.page_request_step(state, { frontmost = false })
			assert.equals("wait", status)
			assert.equals(
				"wait",
				M.page_request_step(state, {
					frontmost = true,
					same_document = true,
					has_pdf_view = true,
					title_valid = true,
					page = 30,
				})
			)
			local ready, page = M.page_request_step(state, {
				frontmost = true,
				same_document = true,
				has_pdf_view = true,
				title_valid = true,
				page = 30,
			})
			assert.equals("ready", ready)
			assert.equals(30, page)
			assert.equals("cancel", M.page_request_step(state, { frontmost = false }))
		end)

		it("keeps waiting when busy or the PDF identity, view, or title is not ready", function()
			local state = {}
			local ready_snapshot = {
				frontmost = true,
				same_document = true,
				has_pdf_view = true,
				title_valid = true,
				page = 30,
			}
			for _, changes in ipairs({
				{ busy = true },
				{ same_document = false },
				{ has_pdf_view = false },
				{ title_valid = false },
			}) do
				local observation = {}
				for key, value in pairs(ready_snapshot) do
					observation[key] = value
				end
				for key, value in pairs(changes) do
					observation[key] = value
				end
				assert.equals("wait", M.page_request_step(state, observation))
			end
			assert.equals("wait", M.page_request_step(state, ready_snapshot))
			local status = M.page_request_step(state, ready_snapshot)
			assert.equals("ready", status)
		end)
	end)

	describe("jump history", function()
		it("keeps order per document and skips duplicate newest entries", function()
			local jumps = {}
			assert.is_true(M.push_jump(jumps, "/a.pdf", 1))
			assert.is_true(M.push_jump(jumps, "/a.pdf", 2))
			assert.is_false(M.push_jump(jumps, "/a.pdf", 2))
			M.push_jump(jumps, "/b.pdf", 9)
			assert.equals(2, M.pop_jump(jumps, "/a.pdf", 3))
			assert.equals(1, M.pop_jump(jumps, "/a.pdf", 3))
			assert.equals(9, M.pop_jump(jumps, "/b.pdf", 3))
		end)

		it("caps each document at MAX_JUMPS", function()
			local jumps = {}
			for page = 1, M.MAX_JUMPS + 5 do
				M.push_jump(jumps, "/paper.pdf", page)
			end
			assert.equals(M.MAX_JUMPS, #jumps["/paper.pdf"])
			assert.equals(6, jumps["/paper.pdf"][1])
		end)

		it("drops entries equal to the current page before popping", function()
			local jumps = { ["/paper.pdf"] = { 1, 2, 3, 3 } }
			assert.equals(2, M.pop_jump(jumps, "/paper.pdf", 3))
			assert.same({ 1 }, jumps["/paper.pdf"])
		end)
	end)

	describe("scroll batches", function()
		it("sums signed half and line steps and tracks fresh presses", function()
			local batch = M.add_scroll(nil, { amount = "half", direction = "down", autorepeat = false })
			batch = M.add_scroll(batch, { amount = "half", direction = "up", autorepeat = true })
			batch = M.add_scroll(batch, { amount = "line", direction = "down", autorepeat = true })
			batch = M.add_scroll(batch, { amount = "line", direction = "up", autorepeat = true })
			assert.same({ half = 0, line = 0, fresh = true }, batch)
			assert.same(
				{ half = 0, line = 1, fresh = false },
				M.add_scroll(nil, {
					amount = "line",
					direction = "down",
					autorepeat = true,
				})
			)
		end)

		it("moves by half a view, one line, and mixed steps", function()
			local geometry = { value = 0.25, view_h = 500, document_h = 1500 }
			local written = nil
			local deps = {
				scroll_geometry = function()
					return geometry
				end,
				set_scroll_value = function(_, value)
					written = value
					return true
				end,
			}
			local half = M.scroll({ half = 1 }, deps)
			assert.equals("done", half.status)
			assert.equals(0.5, half.to)
			assert.equals(half.to, written)

			deps.scroll_geometry = function()
				return geometry
			end
			local line = M.scroll({ line = 1 }, deps)
			assert.equals("done", line.status)
			assert.equals(0.27, line.to)
			local mixed = M.scroll({ half = 1, line = -1 }, deps)
			assert.equals("done", mixed.status)
			assert.equals(0.48, mixed.to)
		end)

		it("clamps to edges without writing when already at an edge", function()
			local writes = 0
			local deps = {
				scroll_geometry = function()
					return { value = 0.9, view_h = 500, document_h = 1500 }
				end,
				set_scroll_value = function()
					writes = writes + 1
					return true
				end,
			}
			assert.equals(1, M.scroll({ half = 1 }, deps).to)
			deps.scroll_geometry = function()
				return { value = 0.1, view_h = 500, document_h = 1500 }
			end
			assert.equals(0, M.scroll({ half = -1 }, deps).to)
			assert.equals(2, writes)
			deps.scroll_geometry = function()
				return { value = 0, view_h = 500, document_h = 1500 }
			end
			assert.equals("edge", M.scroll({ half = -1 }, deps).status)
			assert.equals(2, writes)
			deps.scroll_geometry = function()
				return { value = 0.5, view_h = 500, document_h = 400 }
			end
			assert.equals("edge", M.scroll({ half = 1 }, deps).status)
			assert.equals(2, writes)
		end)

		it("reports geometry, setter, and thrown dependency failures", function()
			local missing = M.scroll({}, {
				scroll_geometry = function()
					return nil, "view unavailable"
				end,
			})
			assert.equals("failed", missing.status)
			assert.equals("view unavailable", missing.reason)
			local rejected = M.scroll({ line = 1 }, {
				scroll_geometry = function()
					return { value = 0, view_h = 500, document_h = 1500 }
				end,
				set_scroll_value = function()
					return false, "bar rejected"
				end,
			})
			assert.equals("failed", rejected.status)
			assert.equals("bar rejected", rejected.reason)
			local thrown = M.scroll({ line = 1 }, {
				scroll_geometry = function()
					return { value = 0, view_h = 500, document_h = 1500 }
				end,
				set_scroll_value = function()
					error("AX failed")
				end,
			})
			assert.equals("failed", thrown.status)
			assert.is_truthy(thrown.reason:find("AX failed", 1, true))
		end)

		it("keeps successful scrolls quiet and formats failures", function()
			assert.is_nil(M.message({ kind = "scroll", status = "done" }))
			assert.is_nil(M.message({ kind = "scroll", status = "edge" }))
			assert.equals(
				"Couldn't scroll the PDF: bar rejected",
				M.message({
					kind = "scroll",
					status = "failed",
					reason = "bar rejected",
				})
			)
		end)
	end)

	describe("jump runner", function()
		it("uses the primary scroll-bar mechanism when it lands", function()
			local state = { page = 10, count = 44, history = M.new_history() }
			local result, env = run_fake(M, { kind = "goto", target = 2 }, state)
			assert.equals("done", result.status)
			assert.equals("scroll_bar", result.via)
			assert.equals(2, state.page)
			assert.same({ 10 }, state.history.back["/paper.pdf"])
			assert.equals(1, env.calls.scroll_to)
		end)

		it("uses AXScrollToVisible when the primary mechanism returns false", function()
			local state = { page = 10, count = 44 }
			state.history = M.new_history()
			local result, env = run_fake(M, { kind = "goto", target = 2 }, state, {
				primary_result = false,
				fallback_lands = true,
			})
			assert.equals("scroll_to_visible", result.via)
			assert.equals(1, env.calls.scroll_to_visible)
			assert.equals(1, #env.logs)
			assert.is_truthy(env.logs[1]:find("scroll%-bar jump missed"))
		end)

		it("falls back after the primary misses its landing deadline", function()
			local state = { page = 10, count = 44 }
			local result, env = run_fake(M, { kind = "goto", target = 2 }, state, {
				primary_lands = false,
				fallback_lands = true,
			})
			assert.equals("scroll_to_visible", result.via)
			assert.is_true(env.now >= M.LAND_TIMEOUT_SECONDS)
		end)

		it("fails when both mechanisms miss or cannot find the PDF view", function()
			local state = { page = 10, count = 44 }
			local missed = run_fake(M, { kind = "goto", target = 2 }, state, {
				primary_lands = false,
				fallback_lands = false,
			})
			assert.equals("didn't reach page 2", missed.reason)

			state = { page = 10, count = 44 }
			local absent = run_fake(M, { kind = "goto", target = 2 }, state, {
				primary_result = false,
				fallback_result = false,
			})
			assert.equals("couldn't find the PDF view", absent.reason)
		end)

		it("rejects an out-of-range count without scrolling or recording history", function()
			local state = { page = 10, count = 44, history = M.new_history() }
			local result, env = run_fake(M, { kind = "goto", target = 50 }, state)
			assert.equals("out_of_range", result.status)
			assert.equals(0, env.calls.scroll_to)
			assert.same({}, state.history.back)
			assert.same({}, state.history.forward)
		end)

		it("reports title-read failure and still scrolls gg on page one", function()
			local state = { page = 10, count = 44 }
			local read_error = run_fake(M, { kind = "goto", target = 2 }, state, {
				page_info = function()
					return nil, "ignored detail"
				end,
			})
			assert.equals("failed", read_error.status)
			assert.equals("couldn't read Highlights' page number", read_error.reason)

			state = { page = 1, count = 44, history = M.new_history() }
			local result, env = run_fake(M, { kind = "goto", target = "first" }, state)
			assert.equals("done", result.status)
			assert.equals(1, env.calls.scroll_to)
			assert.same({}, state.history.back)
		end)

		it("returns empty for an empty back stack and restores a failed back entry", function()
			local state = { page = 2, count = 44, history = M.new_history() }
			local empty = run_fake(M, { kind = "back" }, state)
			assert.equals("empty", empty.status)

			state = { page = 2, count = 44, history = M.new_history() }
			state.history.back = { ["/paper.pdf"] = { 4 } }
			local failed = run_fake(M, { kind = "back" }, state, {
				primary_result = false,
				fallback_result = false,
			})
			assert.equals("failed", failed.status)
			assert.same({ 4 }, state.history.back["/paper.pdf"])
		end)

		it("walks back then forward through two jumps", function()
			local state = { page = 30, count = 44, history = M.new_history() }
			local first = run_fake(M, { kind = "goto", target = 2 }, state)
			assert.equals("done", first.status)
			assert.equals(2, state.page)
			assert.same({ 30 }, state.history.back["/paper.pdf"])
			assert.is_nil(state.history.forward["/paper.pdf"])

			local second = run_fake(M, { kind = "goto", target = 10 }, state)
			assert.equals("done", second.status)
			assert.equals(10, state.page)
			assert.same({ 30, 2 }, state.history.back["/paper.pdf"])

			local back_one = run_fake(M, { kind = "back" }, state)
			assert.equals("done", back_one.status)
			assert.equals(2, back_one.page)
			assert.equals(2, state.page)
			assert.same({ 30 }, state.history.back["/paper.pdf"])
			assert.same({ 10 }, state.history.forward["/paper.pdf"])

			local back_two = run_fake(M, { kind = "back" }, state)
			assert.equals("done", back_two.status)
			assert.equals(30, state.page)
			assert.same({}, state.history.back["/paper.pdf"] or {})
			assert.same({ 10, 2 }, state.history.forward["/paper.pdf"])

			local forward_one = run_fake(M, { kind = "forward" }, state)
			assert.equals("done", forward_one.status)
			assert.equals(2, forward_one.page)
			assert.equals(2, state.page)
			assert.same({ 30 }, state.history.back["/paper.pdf"])
			assert.same({ 10 }, state.history.forward["/paper.pdf"])

			local forward_two = run_fake(M, { kind = "forward" }, state)
			assert.equals("done", forward_two.status)
			assert.equals(10, state.page)
			assert.same({ 30, 2 }, state.history.back["/paper.pdf"])
			assert.same({}, state.history.forward["/paper.pdf"] or {})

			local forward_empty = run_fake(M, { kind = "forward" }, state)
			assert.equals("empty", forward_empty.status)
			assert.equals("forward", forward_empty.kind)
			assert.equals(10, state.page)
		end)

		it("records history only once a jump lands", function()
			local state = { page = 2, count = 44, history = M.new_history() }
			state.history.back = { ["/paper.pdf"] = { 30 } }
			local landed_back = run_fake(M, { kind = "back" }, state)
			assert.equals("done", landed_back.status)
			assert.equals(30, state.page)
			assert.same({ 2 }, state.history.forward["/paper.pdf"])

			state = { page = 2, count = 44, history = M.new_history() }
			state.history.forward = { ["/paper.pdf"] = { 10 } }
			local landed_forward = run_fake(M, { kind = "forward" }, state)
			assert.equals("done", landed_forward.status)
			assert.equals(10, state.page)
			assert.same({ 2 }, state.history.back["/paper.pdf"])
			assert.same({}, state.history.forward["/paper.pdf"] or {})
		end)

		it("clears the forward stack on a new goto after going back", function()
			local state = { page = 30, count = 44, history = M.new_history() }
			run_fake(M, { kind = "goto", target = 2 }, state)
			run_fake(M, { kind = "back" }, state)
			assert.equals(30, state.page)
			assert.same({ 2 }, state.history.forward["/paper.pdf"])
			local jumped = run_fake(M, { kind = "goto", target = 10 }, state)
			assert.equals("done", jumped.status)
			assert.equals(10, state.page)
			assert.same({ 30 }, state.history.back["/paper.pdf"])
			assert.is_nil(state.history.forward["/paper.pdf"])
		end)

		it("leaves the forward stack intact on same-page and out-of-range gotos", function()
			local state = { page = 1, count = 44, history = M.new_history() }
			state.history.forward = { ["/paper.pdf"] = { 9 } }
			local same = run_fake(M, { kind = "goto", target = "first" }, state)
			assert.equals("done", same.status)
			assert.same({ 9 }, state.history.forward["/paper.pdf"])
			assert.same({}, state.history.back["/paper.pdf"] or {})

			state = { page = 10, count = 44, history = M.new_history() }
			state.history.back = { ["/paper.pdf"] = { 30 } }
			state.history.forward = { ["/paper.pdf"] = { 12 } }
			local far = run_fake(M, { kind = "goto", target = 50 }, state)
			assert.equals("out_of_range", far.status)
			assert.same({ 30 }, state.history.back["/paper.pdf"])
			assert.same({ 12 }, state.history.forward["/paper.pdf"])
		end)

		it("restores a failed forward entry without touching the back stack", function()
			local state = { page = 2, count = 44, history = M.new_history() }
			state.history.back = { ["/paper.pdf"] = { 30 } }
			state.history.forward = { ["/paper.pdf"] = { 10 } }
			local failed = run_fake(M, { kind = "forward" }, state, {
				primary_result = false,
				fallback_result = false,
			})
			assert.equals("failed", failed.status)
			assert.same({ 10 }, state.history.forward["/paper.pdf"])
			assert.same({ 30 }, state.history.back["/paper.pdf"])
		end)

		it("leaves the forward stack alone when a back jump fails", function()
			local state = { page = 10, count = 44, history = M.new_history() }
			state.history.back = { ["/paper.pdf"] = { 2 } }
			state.history.forward = { ["/paper.pdf"] = { 12 } }
			local failed = run_fake(M, { kind = "back" }, state, {
				primary_result = false,
				fallback_result = false,
			})
			assert.equals("failed", failed.status)
			assert.same({ 2 }, state.history.back["/paper.pdf"])
			assert.same({ 12 }, state.history.forward["/paper.pdf"])
		end)

		it("leaves both stacks unchanged when a goto fails", function()
			local state = { page = 10, count = 44, history = M.new_history() }
			state.history.back = { ["/paper.pdf"] = { 30 } }
			state.history.forward = { ["/paper.pdf"] = { 12 } }
			local failed = run_fake(M, { kind = "goto", target = 2 }, state, {
				primary_lands = false,
				fallback_lands = false,
			})
			assert.equals("failed", failed.status)
			assert.equals(10, state.page)
			assert.same({ 30 }, state.history.back["/paper.pdf"])
			assert.same({ 12 }, state.history.forward["/paper.pdf"])
		end)

		it("keeps the forward stack per document", function()
			local state = { page = 2, count = 44, history = M.new_history() }
			state.history.forward = { ["/other.pdf"] = { 7 } }
			local empty = run_fake(M, { kind = "forward" }, state)
			assert.equals("empty", empty.status)
			assert.same({ 7 }, state.history.forward["/other.pdf"])
			assert.is_nil(state.history.forward["/paper.pdf"])
		end)

		it("starts from an empty history when the argument is bad", function()
			local state = { page = 10, count = 44, history = { back = false, forward = "nope" } }
			local result = run_fake(M, { kind = "goto", target = 2 }, state)
			assert.equals("done", result.status)
			assert.same({ 10 }, state.history.back["/paper.pdf"])
		end)

		it("re-jumps once after a late restore without replacing the restored-page history", function()
			local state = { page = 30, count = 44, document = "/paper.pdf", history = M.new_history() }
			local env = { now = 0, queue = {}, scroll_calls = 0 }
			local deps = {
				page_info = function()
					return { page = state.page, count = state.count, document = state.document }
				end,
				scroll_to = function(page)
					env.scroll_calls = env.scroll_calls + 1
					state.page = page
					return true
				end,
				scroll_to_visible = function()
					return false
				end,
				landed = function(page)
					return state.page == page
				end,
				same_document = function(path_a, path_b)
					return path_a == path_b
				end,
				after = function(seconds, fn)
					table.insert(env.queue, { seconds = seconds, fn = fn })
				end,
				now = function()
					return env.now
				end,
			}
			local result = nil
			M.run(
				{ kind = "goto", target = 4, origin = "url", document = "/paper.pdf" },
				state.history,
				deps,
				function(value)
					result = value
				end
			)
			-- Highlights restores page 30 after the first successful scroll.
			state.page = 30
			local steps = 0
			while #env.queue > 0 and steps < 20 do
				steps = steps + 1
				local item = table.remove(env.queue, 1)
				env.now = env.now + item.seconds
				item.fn()
			end
			assert.is_true(steps < 20)
			assert.equals("done", result.status)
			assert.equals("url", result.origin)
			assert.equals(4, state.page)
			assert.equals(2, env.scroll_calls)
			assert.same({ 30 }, state.history.back["/paper.pdf"])
			local back_result = nil
			M.run({ kind = "back" }, state.history, deps, function(value)
				back_result = value
			end)
			assert.equals("done", back_result.status)
			assert.equals(30, state.page)
		end)
	end)

	describe("alert copy", function()
		it("keeps successful jumps quiet and reports every other status", function()
			assert.equals("Still jumping pages", M.message({ status = "busy" }))
			assert.is_nil(M.message({ status = "done", page = 2, count = 44 }))
			assert.equals(
				"No page 50 — this PDF has 44 pages",
				M.message({ status = "out_of_range", page = 50, count = 44 })
			)
			assert.equals(
				"No page 2 — this PDF has 1 page",
				M.message({ status = "out_of_range", page = 2, count = 1 })
			)
			assert.equals("No earlier page", M.message({ status = "empty" }))
			assert.equals("No earlier page", M.message({ status = "empty", kind = "back" }))
			assert.equals("No later page", M.message({ status = "empty", kind = "forward" }))
			assert.equals(
				"Couldn't read Highlights' page number",
				M.message({ status = "failed", reason = "couldn't read Highlights' page number" })
			)
			assert.equals(
				"Couldn't jump to page 2: didn't reach page 2",
				M.message({ status = "failed", kind = "goto", page = 2, reason = "didn't reach page 2" })
			)
			assert.equals(
				"Couldn't go back to page 2: didn't reach page 2",
				M.message({ status = "failed", kind = "back", page = 2, reason = "didn't reach page 2" })
			)
			assert.equals(
				"Couldn't go forward to page 2: didn't reach page 2",
				M.message({ status = "failed", kind = "forward", page = 2, reason = "didn't reach page 2" })
			)
		end)

		it("confirms URL jumps and explains the Ctrl-O return page", function()
			assert.equals(
				"Page 4 of 44 · ⌃O back to p. 30",
				M.message({
					status = "done",
					origin = "url",
					page = 4,
					count = 44,
					from = 30,
				})
			)
			assert.equals(
				"Page 1 of 44",
				M.message({
					status = "done",
					origin = "url",
					page = 1,
					count = 44,
					from = 1,
				})
			)
		end)
	end)
end)
