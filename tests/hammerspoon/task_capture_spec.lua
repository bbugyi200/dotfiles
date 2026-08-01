package.path = "./home/dot_hammerspoon/?.lua;" .. package.path

local capture = require("task_capture")

local function assert_request(raw_text, expected)
	local request = capture.parse(raw_text)
	assert.equals(expected.mode, request.mode, raw_text .. " mode")
	assert.equals(expected.text, request.text, raw_text .. " text")
	for key, value in pairs(expected) do
		if key ~= "mode" and key ~= "text" then
			assert.same(value, request[key], raw_text .. " " .. key)
		end
	end
	return request
end

describe("Hammerspoon task capture request model", function()
	it("parses all four canonical Pomodoro forms", function()
		local complete = capture.parse("Do work @Dev:focus-123")
		assert.same({
			mode = "pomodoro",
			text = "Do work",
			route = "dev",
			block_id = "focus-123",
			needs_target = false,
			needs_block_id = false,
		}, complete)

		local needs_id = capture.parse("Do work @Dev:")
		assert.is_false(needs_id.needs_target)
		assert.is_true(needs_id.needs_block_id)
		assert.equals("dev", needs_id.route)

		local needs_target = capture.parse("Do work @:focus-123")
		assert.is_true(needs_target.needs_target)
		assert.is_false(needs_target.needs_block_id)
		assert.equals("focus-123", needs_target.block_id)

		local needs_both = capture.parse("Do work @:")
		assert.is_true(needs_both.needs_target)
		assert.is_true(needs_both.needs_block_id)
	end)

	it("accepts legacy boundary aliases", function()
		local complete = capture.parse("Do work @!Dev:old_id")
		assert.equals("pomodoro", complete.mode)
		assert.equals("dev", complete.route)
		assert.equals("old_id", complete.block_id)

		local route_only = capture.parse("Do work @!Dev")
		assert.equals("pomodoro", route_only.mode)
		assert.equals("dev", route_only.route)
		assert.is_true(route_only.needs_block_id)

		local neither = capture.parse("Do work @!")
		assert.equals("pomodoro", neither.mode)
		assert.is_true(neither.needs_target)
		assert.is_true(neither.needs_block_id)
	end)

	it("parses all four canonical sub-bullet forms", function()
		local complete = capture.parse("Add context @Dev^focus-123")
		assert.same({
			mode = "sub_bullet",
			text = "Add context",
			route = "dev",
			block_id = "focus-123",
			needs_target = false,
			needs_task = false,
		}, complete)

		local needs_task = capture.parse("Add context @Dev^")
		assert.is_false(needs_task.needs_target)
		assert.is_true(needs_task.needs_task)
		assert.equals("dev", needs_task.route)

		local needs_target = capture.parse("Add context @^focus-123")
		assert.is_true(needs_target.needs_target)
		assert.is_false(needs_target.needs_task)
		assert.equals("focus-123", needs_target.block_id)

		local needs_both = capture.parse("Add context @^")
		assert.is_true(needs_both.needs_target)
		assert.is_true(needs_both.needs_task)
	end)

	it("gives sub-bullet markers precedence over Pomodoro markers", function()
		local malformed = capture.parse("Add context @route^bad:id")
		assert.equals("invalid", malformed.mode)
		assert.matches("sub%-bullet", malformed.error)

		local pomodoro = capture.parse("Do work @route:id")
		assert.equals("pomodoro", pomodoro.mode)
		assert.equals("id", pomodoro.block_id)
	end)

	it("rejects invalid sub-bullet components", function()
		for _, raw_text in ipairs({
			"Add context @bad.route^id",
			"Add context @route^bad.id",
			"Add context @route^bad_id",
		}) do
			local request = capture.parse(raw_text)
			assert.equals("invalid", request.mode, raw_text)
			assert.is_truthy(request.error, raw_text)
		end
	end)

	it("rejects invalid Pomodoro components", function()
		for _, raw_text in ipairs({
			"Do work @bad.route:id",
			"Do work @route:bad.id",
			"Do work @route:id:extra",
			"Do work @!:id",
		}) do
			local request = capture.parse(raw_text)
			assert.equals("invalid", request.mode, raw_text)
			assert.is_truthy(request.error, raw_text)
		end
	end)

	it("keeps middle markers literal and marker-only bodies empty", function()
		assert.same({
			text = "Discuss @dev:id later",
			mode = "none",
		}, capture.parse("Discuss @dev:id later"))
		assert.equals("", capture.parse("@dev:id").text)
		assert.equals("", capture.parse("@:").text)
		assert.same({
			text = "Discuss @dev^id later",
			mode = "none",
		}, capture.parse("Discuss @dev^id later"))
		assert.equals("", capture.parse("@dev^id").text)
		assert.equals("", capture.parse("@^").text)
	end)

	it("composes clipboard terminal markers around every picker token", function()
		local cases = {
			{
				token = "@",
				expected = { mode = "note" },
			},
			{
				token = "@#",
				expected = { mode = "note_section" },
			},
			{
				token = "@#Ideas",
				expected = { mode = "note_bullet", prefix = "Ideas" },
			},
			{
				token = "@Notes#",
				expected = { mode = "section", route = "notes" },
			},
			{
				token = "@Dev:focus-123",
				expected = {
					mode = "pomodoro",
					route = "dev",
					block_id = "focus-123",
					needs_target = false,
					needs_block_id = false,
				},
			},
			{
				token = "@Dev:",
				expected = {
					mode = "pomodoro",
					route = "dev",
					needs_target = false,
					needs_block_id = true,
				},
			},
			{
				token = "@:focus-123",
				expected = {
					mode = "pomodoro",
					block_id = "focus-123",
					needs_target = true,
					needs_block_id = false,
				},
			},
			{
				token = "@:",
				expected = {
					mode = "pomodoro",
					needs_target = true,
					needs_block_id = true,
				},
			},
			{
				token = "@!Dev:focus-123",
				expected = {
					mode = "pomodoro",
					route = "dev",
					block_id = "focus-123",
					needs_target = false,
					needs_block_id = false,
				},
			},
			{
				token = "@!Dev",
				expected = {
					mode = "pomodoro",
					route = "dev",
					needs_target = false,
					needs_block_id = true,
				},
			},
			{
				token = "@!",
				expected = {
					mode = "pomodoro",
					needs_target = true,
					needs_block_id = true,
				},
			},
			{
				token = "@Dev^focus-123",
				expected = {
					mode = "sub_bullet",
					route = "dev",
					block_id = "focus-123",
					needs_target = false,
					needs_task = false,
				},
			},
			{
				token = "@Dev^",
				expected = {
					mode = "sub_bullet",
					route = "dev",
					needs_target = false,
					needs_task = true,
				},
			},
			{
				token = "@^focus-123",
				expected = {
					mode = "sub_bullet",
					block_id = "focus-123",
					needs_target = true,
					needs_task = false,
				},
			},
			{
				token = "@^",
				expected = {
					mode = "sub_bullet",
					needs_target = true,
					needs_task = true,
				},
			},
		}
		local clip_markers = { "%", "%03", "%build_log" }

		for _, case in ipairs(cases) do
			for _, marker in ipairs(clip_markers) do
				local expected = {}
				for key, value in pairs(case.expected) do
					expected[key] = value
				end
				expected.text = "Body " .. marker

				assert_request("Body " .. marker .. " " .. case.token, expected)
				assert_request("Body " .. case.token .. " " .. marker, expected)
			end
		end
	end)

	it("preserves crossed clipboard and schedule markers in terminal order", function()
		assert_request("Body @Notes# % s:2", {
			mode = "section",
			text = "Body % s:2",
			route = "notes",
		})
		assert_request("Body @Notes# s:2 %03", {
			mode = "section",
			text = "Body s:2 %03",
			route = "notes",
		})
		assert_request("Body % @Notes# s:2", {
			mode = "section",
			text = "Body % s:2",
			route = "notes",
		})
		assert_request("Body s:2 @Notes# %build_log", {
			mode = "section",
			text = "Body s:2 %build_log",
			route = "notes",
		})
		assert_request("Body @:focus-123 % s:0", {
			mode = "pomodoro",
			text = "Body % s:0",
			block_id = "focus-123",
			needs_target = true,
			needs_block_id = false,
		})
		assert_request("Body @Dev^ s:10 %build_log", {
			mode = "sub_bullet",
			text = "Body s:10 %build_log",
			route = "dev",
			needs_target = false,
			needs_task = true,
		})
	end)

	it("preserves existing note and section descriptors", function()
		assert.same({ text = "Task", mode = "note" }, capture.parse("Task @"))
		assert.same({ text = "Idea", mode = "note_section" }, capture.parse("Idea @#"))
		assert.same({
			text = "Idea",
			mode = "note_bullet",
			prefix = "Ideas",
		}, capture.parse("Idea @#Ideas"))
		assert.same({
			text = "Idea",
			mode = "section",
			route = "notes",
		}, capture.parse("Idea @Notes#"))
		assert.same({
			text = "Idea @notes#time:box",
			mode = "none",
		}, capture.parse("Idea @notes#time:box"))
		assert.same({
			text = "Idea @notes#Ideas",
			mode = "none",
		}, capture.parse("Idea @notes#Ideas"))
		assert.same({ text = "Task @dev", mode = "none" }, capture.parse("Task @dev"))
	end)

	it("converges every form on canonical synthesis", function()
		local expected = "@dev:focus-123 Do work"
		for _, raw_text in ipairs({
			"Do work @Dev:focus-123",
			"Do work @Dev:",
			"Do work @:focus-123",
			"Do work @:",
			"Do work @!Dev:focus-123",
			"Do work @!Dev",
			"Do work @!",
		}) do
			local request = capture.parse(raw_text)
			local final, err = capture.finalize(request, "dev", "focus-123")
			assert.is_nil(err, raw_text)
			assert.equals(expected, final, raw_text)
			assert.is_nil(final:match("@!"), raw_text)
		end
	end)

	it("canonical Pomodoro synthesis retains terminal markers for Bob", function()
		local request = capture.parse("Do work @Dev: % s:2")
		local final, err = capture.finalize(request, nil, "focus-123")
		assert.is_nil(err)
		assert.equals("@dev:focus-123 Do work % s:2", final)
	end)

	it("converges every sub-bullet form on canonical synthesis", function()
		local expected = "@dev^focus-123 Add context"
		for _, raw_text in ipairs({
			"Add context @Dev^focus-123",
			"Add context @Dev^",
			"Add context @^focus-123",
			"Add context @^",
		}) do
			local request = capture.parse(raw_text)
			local final, err = capture.finalize_sub_bullet(request, "dev", "focus-123")
			assert.is_nil(err, raw_text)
			assert.equals(expected, final, raw_text)
		end
	end)

	it("canonical sub-bullet synthesis retains terminal markers for Bob", function()
		local request = capture.parse("Add context s:2 @Dev^ %build_log")
		local final, err = capture.finalize_sub_bullet(request, nil, "focus-123")
		assert.is_nil(err)
		assert.equals("@dev^focus-123 Add context s:2 %build_log", final)
	end)

	it("leaves invalid or unsupported terminal regions to bob capture", function()
		for _, raw_text in ipairs({
			"Idea @Notes# %0",
			"Idea @Notes# %bad.header",
			"Idea @Notes# %18446744073709551616",
			"Idea @Notes# s:18446744073709551616",
			"Idea @Notes# % %3",
			"Idea @Notes# s:1 s:2",
			"Idea @Notes# % s:1 %build_log",
			"Idea @Notes# middle %",
			"Task @dev %",
			"Idea @notes#Ideas %",
		}) do
			assert.same({
				text = raw_text,
				mode = "none",
			}, capture.parse(raw_text), raw_text)
		end
	end)

	it("retains validation failures for the caller to display", function()
		local state = capture.new_state()
		local request = capture.parse("Do work @dev:")
		capture.stage(state, request, nil, nil, "Dev", "area")
		local block_id, err = capture.set_block_id(state, "bad.id")
		assert.is_nil(block_id)
		assert.equals("dev", state.route)
		assert.equals("bad.id", state.block_id)
		assert.matches("block ID", err)

		local final
		final, err = capture.finalize(request, state.route, state.block_id)
		assert.is_nil(final)
		assert.matches("block ID", err)
	end)

	it("clears staged picker values on cancellation", function()
		local state = capture.new_state()
		local request = capture.parse("Do work @:")
		capture.stage(state, request, "dev", "focus-123", "Dev", "area", "24:1f3a9c2b")
		capture.reset(state)
		assert.same({}, state)
	end)

	it("keeps a staged task ref available after capture failure", function()
		local state = capture.new_state()
		local request = capture.parse("Add context @dev^")
		capture.stage(state, request, nil, nil, "Dev", "area", "24:1f3a9c2b")

		-- A CLI failure does not transition or reset the pure request state.
		assert.equals("dev", state.route)
		assert.equals("24:1f3a9c2b", state.task_ref)
		assert.equals("Dev", state.picked_name)
		assert.equals("area", state.picked_kind)
	end)

	it("keeps staged values available after capture failure", function()
		local state = capture.new_state()
		local request = capture.parse("Do work @:focus-123")
		capture.stage(state, request, "dev", nil, "Dev", "area")

		-- A CLI failure does not transition or reset the pure request state.
		assert.equals("dev", state.route)
		assert.equals("focus-123", state.block_id)
		assert.equals("Dev", state.picked_name)
		assert.equals("area", state.picked_kind)
	end)
end)
