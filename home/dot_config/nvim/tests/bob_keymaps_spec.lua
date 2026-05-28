local script_path = debug.getinfo(1, "S").source:sub(2)
local nvim_config_root = vim.fn.fnamemodify(script_path, ":p:h:h")
vim.opt.runtimepath:prepend(nvim_config_root)

local bob_keymaps = require("config.bob_keymaps")

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

local function new_buffer(lines, path, filetype)
	buffer_count = buffer_count + 1
	vim.cmd("enew!")

	local bufnr = vim.api.nvim_get_current_buf()
	vim.api.nvim_buf_set_name(bufnr, path or bob_path("2026/2099020" .. buffer_count .. "_day.md"))
	vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
	vim.bo[bufnr].filetype = filetype or "markdown"

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

do
	local temp_home = vim.fn.tempname()
	vim.fn.mkdir(temp_home .. "/bob", "p")

	with_home(temp_home, function()
		local bob_bufnr = new_buffer({ "# Bob" }, bob_path("note.md"))
		eq(bob_keymaps.is_bob_buffer(bob_bufnr), true, "Bob path is detected")
		eq(bob_keymaps.setup_buffer(bob_bufnr), true, "setup installs for Bob Markdown buffers")
		eq(has_buffer_keymap_desc(bob_bufnr, "Mark Bob Markdown task done"), true, "setup installs task keymaps")

		local outside_bufnr = new_buffer({ "# Outside" }, temp_home .. "/not-bob/note.md")
		eq(bob_keymaps.setup_buffer(outside_bufnr), false, "setup skips paths outside Bob")

		local text_bufnr = new_buffer({ "# Text" }, bob_path("text.txt"), "text")
		eq(bob_keymaps.setup_buffer(text_bufnr), false, "setup skips non-Markdown Bob buffers")
	end)
end

do
	eq(
		bob_keymaps.date_note_path("day", os.time({ year = 2099, month = 1, day = 2, hour = 12 })),
		"2099/20990102_day.md",
		"date helper formats daily path"
	)
end

do
	local line = "- [ ] #task ship it [completion:: 2098-01-01] [cancelled:: 2098-01-01] [other:: yes]"
	eq(
		bob_keymaps.set_task_status_line(line, "x", "2099-01-02"),
		"- [x] #task ship it [completion:: 2099-01-02] [other:: yes]",
		"done task updates completion and removes cancelled"
	)

	eq(
		bob_keymaps.set_task_status_line("- read this [completion:: 2098-01-01]", "-", "2099-01-02"),
		"- [-] read this [cancelled:: 2099-01-02]",
		"cancelled status converts ordinary list item and removes completion"
	)

	eq(
		bob_keymaps.set_task_status_line("- [x] started [completion:: 2098-01-01] [cancelled:: 2098-01-01]", "/"),
		"- [/] started",
		"in-progress status removes terminal date metadata"
	)

	eq(bob_keymaps.set_task_status_line("not a list item", "x", "2099-01-02"), nil, "plain text is ignored")
end

do
	eq(
		bob_keymaps.add_or_update_inline_field("- [ ] task", "completion", "2099-01-02"),
		"- [ ] task [completion:: 2099-01-02]",
		"field helper appends missing field"
	)

	eq(
		bob_keymaps.add_or_update_inline_field("- [ ] task [completion:: 2098-01-01]", "completion", "2099-01-02"),
		"- [ ] task [completion:: 2099-01-02]",
		"field helper updates existing field"
	)

	eq(
		bob_keymaps.remove_inline_field("- [ ] task [completion:: 2098-01-01] [other:: yes]", "completion"),
		"- [ ] task [other:: yes]",
		"field helper removes selected field"
	)
end

do
	local bufnr = new_buffer({
		"- parent",
	})
	vim.api.nvim_win_set_cursor(0, { 1, 0 })
	eq(
		bob_keymaps.insert_line_below(bufnr, "- [ ] #task ", { extra_indent = 2, start_insert = false }),
		"  - [ ] #task ",
		"insert helper adds relative child indentation"
	)
	eq(line_at(bufnr, 2), "  - [ ] #task ", "insert helper writes line below")
	eq(vim.api.nvim_win_get_cursor(0)[2], 13, "insert helper leaves cursor at end")
end

do
	local bufnr = new_buffer({
		"### Existing heading",
		"plain text",
	})

	vim.api.nvim_win_set_cursor(0, { 1, 0 })
	eq(bob_keymaps.set_heading_level(bufnr, 1), true, "heading conversion succeeds")
	eq(line_at(bufnr, 1), "# Existing heading", "heading marker is replaced")

	vim.api.nvim_win_set_cursor(0, { 2, 0 })
	eq(bob_keymaps.set_heading_level(bufnr, 4), true, "plain line heading conversion succeeds")
	eq(line_at(bufnr, 2), "#### plain text", "plain line receives heading marker")
end

do
	local temp_home = vim.fn.tempname()
	local query_links_dir = temp_home .. "/bob/_generated/queries/query/links"
	local zoq_links_dir = temp_home .. "/bob/_generated/queries/zoq/links"
	vim.fn.mkdir(query_links_dir, "p")
	vim.fn.mkdir(zoq_links_dir, "p")
	vim.fn.writefile({ "# Links" }, query_links_dir .. "/source_links.md")
	vim.fn.writefile({ "# Zoq Links" }, zoq_links_dir .. "/fallback_links.md")

	with_home(temp_home, function()
		local bufnr = new_buffer({ "# Source" }, bob_path("source.md"))
		eq(
			bob_keymaps.generated_links_path(bufnr),
			query_links_dir .. "/source_links.md",
			"generated links resolver prefers query links"
		)

		bufnr = new_buffer({ "# Fallback" }, bob_path("fallback.md"))
		eq(
			bob_keymaps.generated_links_path(bufnr),
			zoq_links_dir .. "/fallback_links.md",
			"generated links resolver falls back to zoq links"
		)
	end)
end

do
	local bufnr = new_buffer({
		"- [ ] #task Read [[Some Note]] [completion:: 2098-01-01] ^abc123",
		"## Useful Heading [status:: open]",
		"ordinary line",
	}, bob_path("reference_source.md"))

	eq(
		bob_keymaps.clean_line_text(line_at(bufnr, 1)),
		"#task Read [[Some Note]]",
		"clean line removes list, checkbox, fields, and block ID"
	)

	vim.api.nvim_win_set_cursor(0, { 2, 0 })
	local text, is_reference = bob_keymaps.reference_or_clean_text(bufnr)
	eq(text, "[[reference_source#Useful Heading]]", "heading reference uses note stem and clean heading")
	eq(is_reference, true, "heading reference is marked")

	vim.api.nvim_win_set_cursor(0, { 1, 0 })
	text, is_reference = bob_keymaps.reference_or_clean_text(bufnr)
	eq(text, "[[reference_source#^abc123]]", "block ID reference uses note stem and block ID")
	eq(is_reference, true, "block ID reference is marked")

	vim.api.nvim_win_set_cursor(0, { 3, 0 })
	text, is_reference = bob_keymaps.reference_or_clean_text(bufnr)
	eq(text, "ordinary line", "fallback reference returns clean text")
	eq(is_reference, false, "fallback reference is not marked as reference")
end

for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
	if vim.api.nvim_buf_is_loaded(bufnr) then
		pcall(function()
			vim.bo[bufnr].modified = false
		end)
	end
end

print("bob_keymaps_spec.lua: ok")
