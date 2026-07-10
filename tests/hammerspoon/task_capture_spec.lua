package.path = "./home/dot_hammerspoon/?.lua;" .. package.path

local capture = require("task_capture")

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
		capture.stage(state, request, "dev", "focus-123", "Dev", "area")
		capture.reset(state)
		assert.same({}, state)
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
