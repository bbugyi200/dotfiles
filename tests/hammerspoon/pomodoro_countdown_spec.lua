package.path = "./home/dot_hammerspoon/?.lua;" .. package.path

local countdown = require("pomodoro_countdown")

local function assert_presentation(remaining_seconds, expected_title, expected_appearance, flash_on)
	local presentation = countdown.presentation(remaining_seconds, flash_on)
	assert.equals(expected_title, presentation.title)
	assert.equals(expected_appearance, presentation.appearance)
end

describe("Hammerspoon Pomodoro countdown presentation", function()
	it("formats normal countdowns above zero and at zero", function()
		assert_presentation(601, "10:01", "normal")
		assert_presentation(0, "0:00", "normal")
	end)

	it("formats recently overdue countdowns", function()
		assert_presentation(-1, "+0:01", "overdue")
		assert_presentation(-599, "+9:59", "overdue")
	end)

	it("uses the overdue warning presentation at and beyond the cutoff", function()
		assert.equals(600, countdown.OVERDUE_WARNING_AFTER_SECONDS)
		assert_presentation(-600, "OVERDUE POMODORO", "overdue_warning")
		assert_presentation(-900, "OVERDUE POMODORO", "overdue_warning")
		assert_presentation(-600, "OVERDUE POMODORO", "overdue_warning", false)
		assert_presentation(-900, "OVERDUE POMODORO", "overdue_warning", false)
		assert_presentation(-600, "OVERDUE POMODORO", "overdue_warning_flash", true)
		assert_presentation(-900, "OVERDUE POMODORO", "overdue_warning_flash", true)
	end)

	it("ignores the flash phase outside the overdue warning state", function()
		assert_presentation(601, "10:01", "normal", true)
		assert_presentation(0, "0:00", "normal", true)
		assert_presentation(-1, "+0:01", "overdue", true)
		assert_presentation(-599, "+9:59", "overdue", true)
		assert_presentation(nil, "NO POMODORO", "missing", true)
	end)

	it("uses the missing presentation only without a live countdown", function()
		assert_presentation(nil, "NO POMODORO", "missing")
	end)
end)
