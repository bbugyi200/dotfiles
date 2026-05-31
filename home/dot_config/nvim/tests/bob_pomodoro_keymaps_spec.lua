local script_path = debug.getinfo(1, "S").source:sub(2)
local nvim_config_root = vim.fn.fnamemodify(script_path, ":p:h:h")
vim.opt.runtimepath:prepend(nvim_config_root)

local bob_pomodoro = require("config.bob_pomodoro_keymaps")

local buffer_count = 0

local function eq(actual, expected, label)
	if actual ~= expected then
		error(string.format("%s: expected %q, got %q", label, tostring(expected), tostring(actual)), 2)
	end
end

local function home_path()
	return (vim.env.HOME or vim.fn.expand("~")):gsub("/+$", "")
end

local function bob_path(relative_path)
	return home_path() .. "/bob/" .. relative_path
end

local function with_home(home, callback)
	local previous_home = vim.env.HOME
	vim.env.HOME = home

	local ok, err = pcall(callback)
	vim.env.HOME = previous_home

	if not ok then
		error(err, 0)
	end
end

local function new_buffer(lines, path)
	buffer_count = buffer_count + 1
	vim.cmd("enew!")

	local bufnr = vim.api.nvim_get_current_buf()
	vim.api.nvim_buf_set_name(bufnr, path or bob_path("2026/2099010" .. buffer_count .. "_day.md"))
	vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
	vim.bo[bufnr].filetype = "markdown"

	return bufnr
end

local function line_at(bufnr, lnum)
	return vim.api.nvim_buf_get_lines(bufnr, lnum - 1, lnum, false)[1]
end

local function has_buffer_keymap_desc(bufnr, desc)
	for _, keymap in ipairs(vim.api.nvim_buf_get_keymap(bufnr, "n")) do
		if keymap.desc == desc then
			return true
		end
	end

	return false
end

local sample_lines = {
	"---",
	"type: daily",
	"---",
	"",
	"# 2099-01-01 Thu",
	"",
	"## #gtd",
	"",
	"- [ ] #task outside the ledger",
	"",
	"## Pomodoros ⏱️ 2h5m",
	"",
	"- [x] (1105-1245) #dev done [p:: 15]",
	"- [X] (1345-1410) #dev also done [p:: 5]",
	"- [ ] (1450-1515) #dev first active [p:: 5]",
	"- [ ] (17:45-18:10) #task latest active [[20260528_day]]",
	"- [ ] () #task next placeholder",
	"",
	"## Later",
	"",
	"- [ ] (1900-1925) outside section",
}

do
	local active = assert(bob_pomodoro.find_active_item(sample_lines))
	eq(active.lnum, 16, "latest unchecked timed line is active")
	eq(active.line, "- [ ] (17:45-18:10) #task latest active [[20260528_day]]", "active line text")
end

do
	-- Heading detection is format-agnostic: plain, legacy `[runtime:: …]`, and
	-- the new `⏱️ …` suffix all resolve to the same Pomodoros section.
	local function detects(heading)
		local section = bob_pomodoro.find_pomodoros_section({
			heading,
			"",
			"- [ ] () #task one",
		})
		return section ~= nil and section.heading_lnum == 1
	end

	eq(detects("## Pomodoros"), true, "plain Pomodoros heading is detected")
	eq(detects("## Pomodoros [runtime:: 2h5m]"), true, "legacy runtime heading is detected")
	eq(detects("## Pomodoros ⏱️ 2h5m"), true, "stopwatch runtime heading is detected")
end

do
	local active = assert(bob_pomodoro.find_active_item({
		"# Test",
		"",
		"## Pomodoros",
		"",
		"- [x] (0800-0825) #task completed",
		"- [-] (0830-0855) #task cancelled",
		"- [/] (0900-0925) #task in progress",
		"- [X] (0930-0955) #task completed upper",
	}))
	eq(active.lnum, 7, "in-progress Pomodoro is treated as active")
	eq(active.entry.open, true, "in-progress Pomodoro is open")
end

do
	local next_item = assert(bob_pomodoro.find_next_open_item({
		"# Test",
		"",
		"## Pomodoros",
		"",
		"- [ ] (0800-0825) #task timed open",
		"- [-] () #task cancelled placeholder",
		"- [/] () #task open placeholder",
	}, nil, { prefer_placeholder = true }))
	eq(next_item.lnum, 7, "next-open search prefers open placeholders")
end

do
	local active = assert(bob_pomodoro.find_active_item({
		"# Test",
		"",
		"## Pomodoros",
		"",
		"- [x] (0900-0925) #task completed [p:: 5]",
		"- [ ] () #task placeholder",
	}))
	eq(active.lnum, 6, "placeholder is active when there is no unchecked timed line")
	eq(active.entry.placeholder, true, "placeholder entry is marked")
end

do
	local bufnr = new_buffer(sample_lines)
	vim.api.nvim_win_set_cursor(0, { 16, 0 })

	eq(bob_pomodoro.change_pomodoro_units(bufnr, 2), true, "increment Pomodoro units succeeds")
	eq(
		line_at(bufnr, 16),
		"- [ ] (17:45-18:20) #task latest active [[20260528_day]]",
		"increment extends end time without p metadata"
	)

	eq(bob_pomodoro.change_pomodoro_units(bufnr, -10), true, "decrement Pomodoro units succeeds")
	eq(
		line_at(bufnr, 16),
		"- [ ] (17:45-17:30) #task latest active [[20260528_day]]",
		"decrement moves end time back without p metadata"
	)
end

do
	local bufnr = new_buffer(sample_lines)
	vim.api.nvim_win_set_cursor(0, { 13, 0 })

	eq(bob_pomodoro.offset_time_range(bufnr, 10), true, "offset can edit completed current ledger line")
	eq(line_at(bufnr, 13), "- [x] (1115-1255) #dev done [p:: 15]", "offset preserves compact time style")
end

do
	local bufnr = new_buffer({
		"# Test",
		"",
		"## Pomodoros",
		"",
		"- [ ] (0800-0825) #task legacy [[p:: 3]]",
	})
	vim.api.nvim_win_set_cursor(0, { 5, 0 })

	eq(bob_pomodoro.change_pomodoro_units(bufnr, 2), true, "legacy p metadata line increments time")
	eq(line_at(bufnr, 5), "- [ ] (0800-0835) #task legacy [[p:: 3]]", "legacy p metadata stays unchanged")
end

do
	local bufnr = new_buffer({
		"# Test",
		"",
		"## Pomodoros",
		"",
		"- [ ] (2345-0010) #task near midnight [p:: 1]",
	})
	vim.api.nvim_win_set_cursor(0, { 5, 0 })

	eq(bob_pomodoro.offset_time_range(bufnr, 20), true, "offset wraps across midnight")
	eq(line_at(bufnr, 5), "- [ ] (0005-0030) #task near midnight [p:: 1]", "midnight arithmetic wraps")
end

local lifecycle_lines = {
	"# Test",
	"",
	"## Pomodoros",
	"",
	"- [-] (0800-0825) #task cancelled",
	"- [x] (0830-0855) #task completed",
	"- [/] (0900-0925) #task wip [cancelled:: 2098-01-01]",
	"- [ ] () #task next [completion:: 2098-01-01]",
	"- [ ] () #task later",
	"",
	"## Later",
	"",
	"- [ ] () #task outside section",
}

do
	local bufnr = new_buffer(lifecycle_lines)
	vim.api.nvim_win_set_cursor(0, { 7, 0 })

	eq(bob_pomodoro.complete_and_advance(bufnr, { date = "2099-01-02" }), true, "complete and advance succeeds")
	eq(
		line_at(bufnr, 7),
		"- [x] (0900-0925) #task wip [completion:: 2099-01-02]",
		"completion marks active line done and updates completion metadata"
	)
	eq(vim.api.nvim_win_get_cursor(0)[1], 8, "completion jumps to next open ledger line")
end

do
	local bufnr = new_buffer(lifecycle_lines)
	vim.api.nvim_win_set_cursor(0, { 7, 0 })

	eq(
		bob_pomodoro.complete_and_advance(bufnr, { date = "2099-01-02", next_status = "/" }),
		true,
		"complete and mark next in-progress succeeds"
	)
	eq(line_at(bufnr, 8), "- [/] () #task next", "next line is marked in progress and stale dates removed")
end

do
	local bufnr = new_buffer(lifecycle_lines)
	vim.api.nvim_win_set_cursor(0, { 7, 0 })

	eq(
		bob_pomodoro.complete_and_advance(bufnr, {
			date = "2099-01-02",
			next_status = " ",
			edit_placeholder = true,
			start_insert = false,
		}),
		true,
		"complete and edit next placeholder succeeds"
	)
	eq(line_at(bufnr, 8), "- [ ] () #task next", "next line is normalized to todo")
	eq(vim.api.nvim_win_get_cursor(0)[1], 8, "uppercase lifecycle map keeps cursor on next line")
	eq(
		vim.api.nvim_win_get_cursor(0)[2],
		line_at(bufnr, 8):find("%("),
		"uppercase lifecycle map places cursor inside placeholder"
	)
end

do
	local bufnr = new_buffer(sample_lines)
	eq(bob_pomodoro.setup_buffer(0), true, "setup accepts current buffer 0")
	eq(bob_pomodoro.setup_buffer(bufnr), true, "setup installs for Bob buffers with Pomodoros")
	eq(has_buffer_keymap_desc(bufnr, "Add Bob Pomodoro unit"), true, "setup installs buffer-local keymaps")
	eq(has_buffer_keymap_desc(bufnr, "Complete Bob Pomodoro and jump next"), true, "setup installs lifecycle keymaps")
	eq(bob_pomodoro.jump_to_current(bufnr), true, "jump to active succeeds")
	eq(vim.api.nvim_win_get_cursor(0)[1], 16, "jump moves to latest active timed line")
end

do
	local bufnr = new_buffer(sample_lines)
	vim.api.nvim_win_set_cursor(0, { 15, 0 })

	eq(bob_pomodoro.change_pomodoro_units(0, 1), true, "edit accepts current buffer 0")
	eq(
		line_at(bufnr, 15),
		"- [ ] (1450-1520) #dev first active [p:: 5]",
		"edit with buffer 0 preserves existing p metadata"
	)
end

do
	local bufnr = new_buffer(sample_lines, "/tmp/not-bob.md")
	eq(bob_pomodoro.setup_buffer(bufnr), false, "setup skips non-Bob buffers")
end

do
	with_home("/Users/bbugyi", function()
		local bufnr = new_buffer(sample_lines, bob_path("2026/20260528_day.md"))
		eq(bob_pomodoro.setup_buffer(bufnr), true, "setup installs for macOS-style Bob paths")
		eq(has_buffer_keymap_desc(bufnr, "Add Bob Pomodoro unit"), true, "macOS-style Bob paths get keymaps")
	end)
end

do
	with_home("/Users/bbugyi", function()
		local bufnr = new_buffer(sample_lines, "/Users/bbugyi/not-bob/2026/20260528_day.md")
		eq(bob_pomodoro.setup_buffer(bufnr), false, "setup skips macOS paths outside Bob")
	end)
end

do
	local bufnr = new_buffer({ "# No ledger" })
	eq(bob_pomodoro.setup_buffer(bufnr), false, "setup skips Bob buffers without Pomodoros")
end

for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
	if vim.api.nvim_buf_is_loaded(bufnr) then
		pcall(function()
			vim.bo[bufnr].modified = false
		end)
	end
end

print("bob_pomodoro_keymaps_spec.lua: ok")
