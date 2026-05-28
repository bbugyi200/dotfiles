local M = {}

local open_task_statuses = {
	[" "] = true,
	["/"] = true,
}

local function uv()
	return vim.uv or vim.loop
end

local function normalize_bufnr(bufnr)
	if bufnr == nil or bufnr == 0 then
		return vim.api.nvim_get_current_buf()
	end

	return bufnr
end

local function get_lines(bufnr)
	return vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
end

local function trim(text)
	return (text:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function escape_pattern(text)
	return (text:gsub("([^%w])", "%%%1"))
end

local function with_trailing_slash(path)
	if path:sub(-1) == "/" then
		return path
	end

	return path .. "/"
end

local function notify(message, level)
	vim.notify(message, level or vim.log.levels.INFO, { title = "Bob Markdown" })
end

local function set_repeat(lhs)
	if vim.fn.exists("*repeat#set") == 0 then
		return
	end

	local keys = vim.api.nvim_replace_termcodes(lhs, true, true, true)
	pcall(vim.fn["repeat#set"], keys)
end

function M.normalize_path(path)
	if path == nil or path == "" then
		return nil
	end

	local expanded = vim.fn.fnamemodify(vim.fn.expand(path), ":p")
	return uv().fs_realpath(expanded) or expanded:gsub("/+$", "")
end

function M.bob_root()
	local home = vim.env.HOME
	if home == nil or home == "" then
		home = vim.fn.expand("~")
	end

	return home:gsub("/+$", "") .. "/bob"
end

function M.absolute_bob_path(relative_path)
	local root = M.bob_root():gsub("/+$", "")
	if relative_path == nil or relative_path == "" then
		return root
	end

	if relative_path:sub(1, 1) == "/" then
		return relative_path
	end

	return root .. "/" .. relative_path
end

function M.is_bob_buffer(bufnr)
	bufnr = normalize_bufnr(bufnr)

	local buffer_path = M.normalize_path(vim.api.nvim_buf_get_name(bufnr))
	if buffer_path == nil then
		return false
	end

	local root = M.normalize_path(M.bob_root()) or M.bob_root()
	root = with_trailing_slash(root)

	return buffer_path:sub(1, #root) == root
end

function M.iso_date(time)
	return os.date("%Y-%m-%d", time)
end

function M.date_note_path(kind, time)
	local date = os.date("*t", time)
	return string.format("%04d/%04d%02d%02d_%s.md", date.year, date.year, date.month, date.day, kind)
end

function M.today_day_path(time)
	return M.date_note_path("day", time)
end

function M.today_habit_path(time)
	return M.date_note_path("habit", time)
end

function M.today_done_path(time)
	return M.date_note_path("done", time)
end

function M.note_stem(bufnr)
	bufnr = normalize_bufnr(bufnr)

	local name = vim.api.nvim_buf_get_name(bufnr)
	if name == nil or name == "" then
		return nil
	end

	return vim.fn.fnamemodify(name, ":t:r")
end

function M.open_path(path, opts)
	opts = opts or {}

	local command = "edit"
	if opts.split == "vertical" then
		command = "vsplit"
	elseif opts.split == "horizontal" then
		command = "split"
	end

	vim.cmd(command .. " " .. vim.fn.fnameescape(path))

	if opts.at_eof then
		vim.cmd("normal! G")
	end

	if opts.first_open_task then
		M.jump_to_first_open_task(0)
	end

	return path
end

function M.open_bob_path(relative_path, opts)
	return M.open_path(M.absolute_bob_path(relative_path), opts)
end

function M.parse_list_item(line)
	local indent, bullet, rest = line:match("^(%s*)([-*+])%s+(.*)$")
	if indent == nil then
		return nil
	end

	local checkbox, text = rest:match("^%[([^%]])%]%s*(.*)$")
	if checkbox ~= nil then
		return {
			indent = indent,
			bullet = bullet,
			checkbox = checkbox,
			text = text,
		}
	end

	return {
		indent = indent,
		bullet = bullet,
		checkbox = nil,
		text = rest,
	}
end

function M.remove_inline_field(line, field)
	local field_pattern = escape_pattern(field)
	line = line:gsub("%s*%[%[" .. field_pattern .. "::%s*[^%]]-%]%]", "")
	line = line:gsub("%s*%[" .. field_pattern .. "::%s*[^%]]-%]", "")
	return line:gsub("%s+$", "")
end

function M.add_or_update_inline_field(line, field, value)
	local field_pattern = escape_pattern(field)
	local metadata = "[" .. field .. ":: " .. value .. "]"
	local new_line, replacements = line:gsub("%[%[" .. field_pattern .. "::%s*[^%]]-%]%]", metadata, 1)

	if replacements > 0 then
		return new_line:gsub("%s+$", "")
	end

	new_line, replacements = line:gsub("%[" .. field_pattern .. "::%s*[^%]]-%]", metadata, 1)
	if replacements > 0 then
		return new_line:gsub("%s+$", "")
	end

	if line:match("%S$") then
		return line .. " " .. metadata
	end

	return line .. metadata
end

function M.set_task_status_line(line, status, date)
	local item = M.parse_list_item(line)
	if item == nil then
		return nil
	end

	local new_line = item.indent .. item.bullet .. " [" .. status .. "] " .. item.text

	if status == "x" then
		new_line = M.remove_inline_field(new_line, "cancelled")
		new_line = M.add_or_update_inline_field(new_line, "completion", date or M.iso_date())
	elseif status == "-" then
		new_line = M.remove_inline_field(new_line, "completion")
		new_line = M.add_or_update_inline_field(new_line, "cancelled", date or M.iso_date())
	elseif status == "/" then
		new_line = M.remove_inline_field(new_line, "completion")
		new_line = M.remove_inline_field(new_line, "cancelled")
	end

	return new_line
end

function M.set_current_task_status(bufnr, status, opts)
	bufnr = normalize_bufnr(bufnr)
	opts = opts or {}

	local lnum = vim.api.nvim_win_get_cursor(0)[1]
	local line = vim.api.nvim_buf_get_lines(bufnr, lnum - 1, lnum, false)[1]
	if line == nil then
		notify("No line under cursor", vim.log.levels.WARN)
		return false
	end

	local new_line = M.set_task_status_line(line, status, opts.date)
	if new_line == nil then
		notify("Current line is not a Markdown list item", vim.log.levels.WARN)
		return false
	end

	vim.api.nvim_buf_set_lines(bufnr, lnum - 1, lnum, false, { new_line })
	return true
end

function M.insert_line_below(bufnr, text, opts)
	bufnr = normalize_bufnr(bufnr)
	opts = opts or {}

	local lnum = vim.api.nvim_win_get_cursor(0)[1]
	local current_line = vim.api.nvim_buf_get_lines(bufnr, lnum - 1, lnum, false)[1] or ""
	local indent = current_line:match("^(%s*)") or ""
	local new_line = indent .. string.rep(" ", opts.extra_indent or 0) .. text

	vim.api.nvim_buf_set_lines(bufnr, lnum, lnum, false, { new_line })
	vim.api.nvim_win_set_cursor(0, { lnum + 1, #new_line })

	if opts.start_insert ~= false then
		vim.cmd("startinsert!")
	end

	return new_line
end

function M.set_heading_level(bufnr, level)
	bufnr = normalize_bufnr(bufnr)

	local lnum = vim.api.nvim_win_get_cursor(0)[1]
	local line = vim.api.nvim_buf_get_lines(bufnr, lnum - 1, lnum, false)[1]
	if line == nil then
		return false
	end

	local text = line:gsub("^%s*#+%s*", ""):gsub("^%s+", "")
	vim.api.nvim_buf_set_lines(bufnr, lnum - 1, lnum, false, { string.rep("#", level) .. " " .. text })
	return true
end

function M.find_first_open_task(lines)
	for lnum, line in ipairs(lines) do
		local item = M.parse_list_item(line)
		if item ~= nil and open_task_statuses[item.checkbox] then
			return {
				lnum = lnum,
				line = line,
				item = item,
			}
		end
	end

	return nil
end

function M.jump_to_first_open_task(bufnr)
	bufnr = normalize_bufnr(bufnr)

	local item = M.find_first_open_task(get_lines(bufnr))
	if item == nil then
		notify("No open Markdown task found")
		return false
	end

	vim.api.nvim_win_set_cursor(0, { item.lnum, 0 })
	return true
end

function M.generated_links_path(bufnr)
	bufnr = normalize_bufnr(bufnr)

	local stem = M.note_stem(bufnr)
	if stem == nil or stem == "" then
		return nil
	end

	local candidates = {
		M.absolute_bob_path("_generated/queries/query/links/" .. stem .. "_links.md"),
		M.absolute_bob_path("_generated/queries/zoq/links/" .. stem .. "_links.md"),
	}

	for _, path in ipairs(candidates) do
		if uv().fs_stat(path) ~= nil then
			return path
		end
	end

	return nil
end

function M.open_generated_links_or_backlinks(bufnr, opts)
	bufnr = normalize_bufnr(bufnr)
	opts = opts or {}

	local path = M.generated_links_path(bufnr)
	if path ~= nil then
		return M.open_path(path, { split = opts.split })
	end

	M.run_obsidian_command({ "backlinks" })
	return nil
end

function M.run_obsidian_command(args)
	vim.api.nvim_cmd({ cmd = "Obsidian", args = args }, {})
end

function M.open_obsidian_search_for_stem(bufnr)
	local stem = M.note_stem(bufnr)
	if stem == nil or stem == "" then
		notify("No note stem to search for", vim.log.levels.WARN)
		return false
	end

	M.run_obsidian_command({ "search", stem })
	return true
end

function M.clean_line_text(line)
	local text = trim(line)
	text = text:gsub("^#+%s*", "")
	text = text:gsub("^[-*+]%s+", "")
	text = text:gsub("^%[[^%]]%]%s*", "")
	text = text:gsub("%s*%^[%w_-]+%s*$", "")
	text = text:gsub("%s*%[%[[%w_/%- ]+::%s*[^%]]-%]%]", "")
	text = text:gsub("%s*%[[%w_/%- ]+::%s*[^%]]-%]", "")
	text = text:gsub("%s+", " ")
	return trim(text)
end

function M.reference_or_clean_text(bufnr)
	bufnr = normalize_bufnr(bufnr)

	local stem = M.note_stem(bufnr)
	local lnum = vim.api.nvim_win_get_cursor(0)[1]
	local line = vim.api.nvim_buf_get_lines(bufnr, lnum - 1, lnum, false)[1]
	if line == nil then
		return nil, false
	end

	if stem ~= nil and stem ~= "" then
		local heading = line:match("^%s*#+%s*(.-)%s*$")
		if heading ~= nil then
			heading = M.clean_line_text(heading)
			if heading ~= "" then
				return "[[" .. stem .. "#" .. heading .. "]]", true
			end
		end

		local block_id = line:match("%s%^(%w[%w_-]*)%s*$") or line:match("^%s*%^(%w[%w_-]*)%s*$")
		if block_id ~= nil then
			return "[[" .. stem .. "#^" .. block_id .. "]]", true
		end
	end

	local cleaned = M.clean_line_text(line)
	if cleaned == "" then
		return nil, false
	end

	return cleaned, false
end

function M.copy_text(text, append)
	local mode = append and "a" or "c"
	local ok = pcall(vim.fn.setreg, "+", text, mode)
	if not ok then
		vim.fn.setreg('"', text, mode)
	end

	return text
end

function M.copy_current_clean_line(bufnr, append)
	bufnr = normalize_bufnr(bufnr)

	local lnum = vim.api.nvim_win_get_cursor(0)[1]
	local line = vim.api.nvim_buf_get_lines(bufnr, lnum - 1, lnum, false)[1]
	if line == nil then
		notify("No line under cursor", vim.log.levels.WARN)
		return nil
	end

	local text = M.clean_line_text(line)
	if text == "" then
		notify("No Markdown line text to copy", vim.log.levels.WARN)
		return nil
	end

	return M.copy_text(text .. "\n", append)
end

function M.copy_current_reference(bufnr, append)
	bufnr = normalize_bufnr(bufnr)

	local text, is_reference = M.reference_or_clean_text(bufnr)
	if text == nil then
		notify("No Markdown reference or line text to copy", vim.log.levels.WARN)
		return nil
	end

	if not is_reference then
		notify("No heading or block ID found; copied cleaned line text")
	end

	return M.copy_text(text .. "\n", append)
end

local function set_keymap(bufnr, lhs, rhs, desc, opts)
	local keymap_opts = {
		buffer = bufnr,
		nowait = true,
		desc = desc,
	}

	if opts ~= nil then
		keymap_opts = vim.tbl_extend("force", keymap_opts, opts)
	end

	vim.keymap.set("n", lhs, rhs, keymap_opts)
end

local function insert_map(bufnr, lhs, text, desc, extra_indent)
	set_keymap(bufnr, lhs, function()
		M.insert_line_below(bufnr, text, { extra_indent = extra_indent or 0 })
	end, desc)
end

function M.setup_buffer(bufnr)
	bufnr = normalize_bufnr(bufnr)

	if vim.bo[bufnr].filetype ~= "markdown" then
		return false
	end

	if not M.is_bob_buffer(bufnr) then
		return false
	end

	set_keymap(bufnr, "<leader>zx", function()
		M.set_current_task_status(bufnr, "x")
	end, "Mark Bob Markdown task done")

	set_keymap(bufnr, "<leader>zX", function()
		M.set_current_task_status(bufnr, "-")
	end, "Mark Bob Markdown task cancelled")

	set_keymap(bufnr, "<leader>z8", function()
		M.set_current_task_status(bufnr, "/")
	end, "Mark Bob Markdown task in progress")

	insert_map(bufnr, "<leader>zn", "- ", "Insert Bob bullet")
	insert_map(bufnr, "<leader>zo", "- [ ] #task ", "Insert Bob task")
	insert_map(bufnr, "<leader>z0", "- [ ] #task [gtd-pri:: P0] ", "Insert Bob P0 task")
	insert_map(bufnr, "<leader>z1", "- [ ] #task [gtd-pri:: P1] ", "Insert Bob P1 task")
	insert_map(bufnr, "<leader>z2", "- [ ] #task [gtd-pri:: P2] ", "Insert Bob P2 task")
	insert_map(bufnr, "<leader>z3", "- [ ] #task [gtd-pri:: P3] ", "Insert Bob P3 task")
	insert_map(bufnr, "<leader>z[", "- ", "Insert Bob child bullet", 2)
	insert_map(bufnr, "<leader>z]", "- [ ] #task ", "Insert Bob child task", 2)
	insert_map(bufnr, "<leader>z}", "- [ ] #task ", "Insert deeper Bob child task", 4)
	insert_map(bufnr, "<leader>z-", "- ", "Insert deeper Bob child bullet", 4)
	insert_map(bufnr, "<leader>z=", "- ", "Insert deepest Bob child bullet", 6)
	insert_map(bufnr, "<leader>zf", "- [file:: ]", "Insert Bob file field")
	insert_map(bufnr, "<leader>zl", "- [related:: ]", "Insert Bob related field")
	insert_map(bufnr, "<leader>zr", "- [tick:: ]", "Insert Bob tick field")
	insert_map(bufnr, "<leader>zs", "- [status:: ]", "Insert Bob status field")
	insert_map(bufnr, "<leader>zt", "- [title:: ]", "Insert Bob title field")
	insert_map(bufnr, "<leader>zu", "- [url:: ]", "Insert Bob URL field")

	set_keymap(bufnr, "<leader>zgd", function()
		M.open_bob_path(M.today_day_path())
	end, "Open today's Bob daily note")

	set_keymap(bufnr, "<leader>zgh", function()
		M.open_bob_path(M.today_habit_path())
	end, "Open today's Bob habit note")

	set_keymap(bufnr, "<leader>zgx", function()
		M.open_bob_path(M.today_done_path())
	end, "Open today's Bob done note")

	set_keymap(bufnr, "gn", function()
		M.open_bob_path("")
	end, "Open Bob vault root")

	set_keymap(bufnr, "gO", function()
		M.open_bob_path("inbox.md", { first_open_task = true })
	end, "Open Bob inbox")

	set_keymap(bufnr, "g.h2", function()
		M.open_bob_path("h2_role.md")
	end, "Open Bob H2 roles")

	set_keymap(bufnr, "g.h3", function()
		M.open_bob_path("h3_goal.md")
	end, "Open Bob H3 goals")

	set_keymap(bufnr, "g.h4", function()
		M.open_bob_path("h4_vision.md")
	end, "Open Bob H4 vision")

	set_keymap(bufnr, "g.h5", function()
		M.open_bob_path("h5_life.md")
	end, "Open Bob H5 life")

	set_keymap(bufnr, "g.k", function()
		M.open_bob_path("z_key.md")
	end, "Open Bob key note")

	set_keymap(bufnr, "g.m", function()
		M.open_bob_path("maybe.md", { at_eof = true })
	end, "Open Bob maybe at EOF")

	set_keymap(bufnr, "g.M", function()
		M.open_bob_path("maybe.md")
	end, "Open Bob maybe")

	set_keymap(bufnr, "g.p", function()
		M.open_bob_path("prj.md")
	end, "Open Bob projects")

	set_keymap(bufnr, "g.q", function()
		M.open_bob_path("_generated/queries/Index.md")
	end, "Open Bob query index")

	set_keymap(bufnr, "g.u", function()
		M.open_bob_path("url.md", { at_eof = true })
	end, "Open Bob URLs at EOF")

	set_keymap(bufnr, "g.x", function()
		M.open_bob_path("tmp.md")
	end, "Open Bob temp note")

	set_keymap(bufnr, "<leader><cr>", function()
		local ok, obsidian_api = pcall(require, "obsidian.api")
		if ok and obsidian_api.smart_action ~= nil then
			return obsidian_api.smart_action()
		end

		return "<cmd>Obsidian follow_link<cr>"
	end, "Obsidian smart action", { expr = true })

	set_keymap(bufnr, "g0", function()
		M.run_obsidian_command({ "links" })
	end, "Show Bob note outgoing links")

	set_keymap(bufnr, "g1", function()
		M.open_generated_links_or_backlinks(bufnr)
	end, "Open Bob generated links or backlinks")

	set_keymap(bufnr, "g2", function()
		M.open_generated_links_or_backlinks(bufnr, { split = "vertical" })
	end, "Open Bob generated links or backlinks in vertical split")

	set_keymap(bufnr, "g3", function()
		M.open_obsidian_search_for_stem(bufnr)
	end, "Search Bob vault for current note stem")

	set_keymap(bufnr, "<localleader>q", ":Obsidian search ", "Start Obsidian vault search")

	set_keymap(bufnr, "<localleader>Q", function()
		M.open_bob_path("_generated/queries/Index.md")
	end, "Open Bob query index")

	for level = 1, 4 do
		set_keymap(bufnr, ",H" .. level, function()
			M.set_heading_level(bufnr, level)
		end, "Convert line to Markdown H" .. level)
	end

	set_keymap(bufnr, "<localleader>c", function()
		M.copy_current_clean_line(bufnr, false)
	end, "Copy cleaned Bob Markdown line")

	set_keymap(bufnr, "<localleader>z", function()
		M.copy_current_reference(bufnr, false)
	end, "Copy Bob Markdown reference")

	set_keymap(bufnr, "<localleader>Z", function()
		M.copy_current_reference(bufnr, true)
		set_repeat("<localleader>Z")
	end, "Append Bob Markdown reference")

	return true
end

return M
