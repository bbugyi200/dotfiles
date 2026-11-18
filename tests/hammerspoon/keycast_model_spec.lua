local MODEL_PATH = "home/dot_hammerspoon/keycast_model.lua"
local model = assert(loadfile(MODEL_PATH))()

local function event(key, modifiers, extra)
	local result = { key = key, modifiers = modifiers or {} }
	for name, value in pairs(extra or {}) do
		result[name] = value
	end
	return result
end

describe("keycast model constants and tokens", function()
	it("defines modes, privacy timing, and the two recorder chords", function()
		assert.equals("all", model.DEFAULT_MODE)
		assert.same({ all = true, chords = true, off = true }, model.MODES)
		assert.equals(2, model.ENTRY_TTL)
		assert.equals(320, model.MIN_REGION_WIDTH)
		assert.equals(120, model.MIN_REGION_HEIGHT)
		assert.equals(2, #model.RECORDER_CHORDS)
		assert.equals("v", model.RECORDER_CHORDS[1].key)
		assert.equals("s", model.RECORDER_CHORDS[2].key)
	end)

	it("turns key names and macOS key codes into readable labels", function()
		assert.equals("a", model.keyToken("a").label)
		assert.equals("⌃A", model.keyToken("a", { "control" }).label)
		assert.equals("⌘Z", model.keyToken("z", { cmd = true, shift = true }).label)
		assert.equals("↩︎", model.keyToken("return").label)
		assert.equals("⎋", model.keyToken("esc").label)
		assert.equals("←", model.keyToken(123).label)
		assert.equals("q", model.keyToken(0, {}, "q").label)
		assert.is_nil(model.keyToken("shift"))
		assert.is_nil(model.keyToken(999))
	end)

	it("normalizes modifier aliases and ignores unknown flags", function()
		assert.same(
			{ ctrl = true, alt = true, shift = true },
			model.normalizeModifiers({ control = true, option = true, shift = true, bogus = true })
		)
	end)
end)

describe("keycast filtering and privacy", function()
	it("filters ordinary typing according to all, chords, and off modes", function()
		assert.equals("x", model.filter("all", event("x")).label)
		assert.is_nil(model.filter("chords", event("x")))
		assert.equals("⌃X", model.filter("chords", event("x", { ctrl = true })).label)
		assert.is_nil(model.filter("chords", event("x", { shift = true })))
		assert.is_nil(model.filter("off", event("x", { cmd = true })))
		assert.equals("all", model.normalizeMode("unexpected"))
	end)

	it("excludes both recorder chords and bare modifier presses", function()
		local recorder_modifiers = { ctrl = true, alt = true, shift = true }
		assert.is_true(model.isRecorderChord("v", recorder_modifiers))
		assert.is_true(model.isRecorderChord("s", recorder_modifiers))
		assert.is_false(model.isRecorderChord("a", recorder_modifiers))
		assert.is_false(model.isRecorderChord("v", { ctrl = true, alt = true }))
		assert.is_nil(model.filter("all", event("v", recorder_modifiers)))
		assert.is_nil(model.filter("all", event("s", recorder_modifiers)))
		assert.is_nil(model.filter("all", event("cmd")))
	end)

	it("rejects non-keyDown events", function()
		assert.is_nil(model.filter("all", event("a", {}, { type = "flagsChanged" })))
		assert.equals("a", model.filter("all", event("a", {}, { type = "keyDown" })).label)
	end)

	it("matches denied app names and bundle identifiers case-insensitively", function()
		for _, app in ipairs({
			"1Password",
			"1Password 8",
			"Keychain Access",
			"Passwords",
			"Bitwarden",
			"com.agilebits.onepassword7",
			"com.apple.keychainaccess",
			"com.apple.Passwords",
			"com.bitwarden.desktop",
		}) do
			assert.is_true(model.isDeniedApp(app), app)
			assert.is_nil(model.filter("all", event("a"), app))
		end
		assert.is_false(model.isDeniedApp("Visual Studio Code"))
	end)

	it("clears the trail immediately for denied apps, secure input, and off mode", function()
		local trail = {
			{ label = "secret", text = "secret", at = 1, updated_at = 1 },
		}
		local denied = model.update(trail, event("a"), 1.1, "all", "1Password")
		assert.same({}, denied)
		local secure = model.update(trail, event("a", {}, { secure = true }), 1.1, "all")
		assert.same({}, secure)
		local off = model.update(trail, event("a"), 1.1, "off")
		assert.same({}, off)
	end)
end)

describe("keycast trail", function()
	it("coalesces quick printable runs without mutating its input", function()
		local trail = {}
		for index, char in ipairs({ "c", "i", "w", "f", "o", "o" }) do
			trail = model.update(trail, event(char), 1 + index * 0.1, "all")
		end
		assert.equals(1, #trail)
		assert.equals("ciwfoo", trail[1].label)
		assert.equals("o", trail[1].key)

		local original = { { kind = "text", key = "a", text = "a", label = "a", count = 1, at = 1 } }
		local next_trail = model.append(original, model.token(event("b")), 1.1)
		assert.equals("a", original[1].label)
		assert.equals("ab", next_trail[1].label)
	end)

	it("collapses autorepeat into a counted token", function()
		local trail = model.update({}, event("j"), 1, "all")
		trail = model.update(trail, event("j", {}, { ["repeat"] = true }), 1.1, "all")
		assert.equals(1, #trail)
		assert.equals("j ×2", trail[1].label)
		assert.equals(2, trail[1].count)
		trail = model.update(trail, event("j", {}, { ["repeat"] = true }), 1.2, "all")
		assert.equals("j ×3", trail[1].label)
	end)

	it("keeps repeated characters separate from an adjacent printable run", function()
		local trail = model.update({}, event("c"), 1, "all")
		trail = model.update(trail, event("i"), 1.1, "all")
		trail = model.update(trail, event("w"), 1.2, "all")
		trail = model.update(trail, event("w", {}, { ["repeat"] = true }), 1.3, "all")
		assert.equals(2, #trail)
		assert.equals("ci", trail[1].label)
		assert.equals("w ×2", trail[2].label)
	end)

	it("does not coalesce printable keys after the coalescing window", function()
		local trail = model.update({}, event("c"), 1, "all")
		trail = model.update(trail, event("i"), 1 + model.COALESCE_WINDOW + 0.01, "all")
		assert.equals(2, #trail)
	end)

	it("expires entries two seconds after their latest update", function()
		local trail = model.update({}, event("a"), 1, "all")
		trail = model.update(trail, event("b"), 1.2, "all")
		assert.equals(1, #model.expire(trail, 3.19))
		assert.same({}, model.expire(trail, 3.2))
	end)

	it("keeps chord tokens distinct from printable text runs", function()
		local trail = model.update({}, event("a", { ctrl = true }), 1, "all")
		trail = model.update(trail, event("b"), 1.1, "all")
		assert.equals(2, #trail)
		assert.equals("⌃A", trail[1].label)
		assert.equals("b", trail[2].label)
	end)
end)

describe("keycast region layout", function()
	it("places the line in the bottom-right with the specified font sizing", function()
		local region = { x = 100, y = 200, w = 800, h = 500 }
		local layout = model.layout(region)
		assert.is_true(layout.visible)
		assert.equals("bottom_right", layout.anchor)
		assert.equals(16, layout.font_size)
		assert.equals(480, layout.frame.w)
		assert.equals(region.x + region.w - 16 - layout.frame.w, layout.frame.x)
		assert.equals(region.y + region.h - 76 - layout.frame.h, layout.frame.y)
		assert.is_true(layout.frame.x >= region.x)
		assert.is_true(layout.frame.y >= region.y)
		assert.is_true(layout.frame.x + layout.frame.w <= region.x + region.w)
		assert.is_true(layout.frame.y + layout.frame.h <= region.y + region.h)
	end)

	it("clamps the font size and measured content width", function()
		local small_height = model.layout({ x = 0, y = 0, w = 320, h = 120 }, 900)
		assert.equals(16, small_height.font_size)
		assert.equals(288, small_height.frame.w)
		local large_height = model.layout({ x = 0, y = 0, w = 900, h = 1600 }, 120)
		assert.equals(28, large_height.font_size)
		assert.equals(120, large_height.frame.w)
	end)

	it("suppresses undersized and invalid regions", function()
		local too_narrow = model.layout({ x = 0, y = 0, w = 319, h = 500 })
		local too_short = model.layout({ x = 0, y = 0, w = 500, h = 119 })
		local invalid = model.layout({ x = 0, y = 0, w = -1, h = 200 })
		assert.is_false(too_narrow.visible)
		assert.equals("region too small", too_narrow.reason)
		assert.is_false(too_short.visible)
		assert.equals("invalid region", invalid.reason)
	end)
end)
