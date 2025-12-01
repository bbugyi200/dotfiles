require("luasnip.loaders.from_lua").load({ paths = { "~/org/cfg/luasnippets" } })

local run_open_zorg_action = require("zorg.util.run_open_zorg_action")
local bb = require("bb_utils")

--- Deletes the extension ".zo" if it is positioned directly before the cursor.
local function delete_dot_zo_before_cursor()
	local cursor = vim.api.nvim_win_get_cursor(0)
	local row, col = cursor[1], cursor[2]

	-- If there's not enough room to have ".zo" before the cursor, do nothing.
	if col < 3 then
		return
	end

	-- Get the entire line's text.
	local line = vim.api.nvim_get_current_line()

	-- In Lua's string functions, indexing is 1-based, but 'col' is the number
	-- of characters from the start of the line in 0-based.
	-- The substring from col-2 to col in 1-based indices gives
	-- the three characters ending exactly before the cursor.
	if line:sub(col - 2, col) == ".zo" then
		-- Remove ".zo" from the line.
		-- line:sub(1, col-3) is everything before ".zo",
		-- line:sub(col+1) is everything after ".zo".
		local new_line = line:sub(1, col - 3) .. line:sub(col + 1)

		-- Set the updated line in the buffer.
		vim.api.nvim_set_current_line(new_line)

		-- Move the cursor left by 3 columns to account for the removed characters.
		vim.api.nvim_win_set_cursor(0, { row, col - 3 })
	end
end

--- Interprets the forward slash key press for intelligent file path completion.
---
--- This function checks the character before the cursor and determines whether
--- to trigger file-name completion or simply return a forward slash.
---
---@return string # Either a sequence to trigger file-name completion or a single forward slash.
local function interpret_forward_slash()
	-- Get the character immediately before the cursor
	local last_ch = vim.fn.matchstr(vim.fn.getline("."), "\\%" .. (vim.fn.col(".") - 1) .. "c.")

	-- If last_ch is '~', '.' or alphanumeric, or if the popup menu is visible,
	-- then trigger file-name completion; otherwise, just return "/".
	if last_ch == "~" or last_ch == "." or vim.fn.pumvisible() == 1 or last_ch:match("[A-Za-z0-9]") then
		-- Notice double backslashes to avoid Lua string-escape issues
		return "/<C-x><C-f><C-p>"
	end

	return "/"
end

--- Extracts the Zorg note ZID from a given line of text.
---
---@param line string The line of text to search for a Zorg note ZID.
---@return string|nil # The extracted Zorg note ZID if found, or nil if not found.
local function get_zorg_note_zid(line)
	-- Using Vim’s regex engine through vim.fn.matchstr
	-- Pattern: '\v([0-9]{6})? \zs[0-9]{6}#[0-9A-Za-z]{2}'
	-- (the \v means "very magic" in Vim regex syntax)
	return vim.fn.matchstr(line, [[\v([0-9]{6})? \zs[0-9]{6}#[0-9A-Za-z]{2}]])
end

---@return string # The stem of the current file name (basename without extension).
local function get_current_file_stem()
	local file_path = vim.fn.expand("%:t")
	return file_path:match("(.+)%..+$") or file_path
end

--- Processes a line from a Zorg note, removing specific patterns.
---
---@param line string The input line from a Zorg note
---@return string # The processed line with specific patterns removed
local function get_zorg_note_copy(line)
	-- 1) Remove e.g. " 202501 202501#AB" from the line
	local zorg_note_copy = vim.fn.substitute(line, [[\v( [0-9]{6})? [0-9]{6}#[0-9A-Za-z]{2}]], "", "")
	-- 2) Remove " @WIP"
	zorg_note_copy = vim.fn.substitute(zorg_note_copy, [[ @WIP]], "", "")
	-- 3) Remove " | RID::..."
	zorg_note_copy = vim.fn.substitute(zorg_note_copy, [[\v \| RID::[0-9A-Za-z_]+]], "", "")
	-- 4) Remove surrounding whitespace.
	zorg_note_copy = vim.fn.substitute(zorg_note_copy, [[^\v(\s*|\s*$)]], "", "")
	-- 5) Convert ID::foobar to [#foobar].
	zorg_note_copy = vim.fn.substitute(zorg_note_copy, [[ ID::\([0-9A-Za-z_]\+\)]], " [#\\1]", "g")
	-- 6) Convert LID::bar in file foo.zo to [[foo#bar]].
	local current_file = get_current_file_stem()
	zorg_note_copy =
		vim.fn.substitute(zorg_note_copy, [[ LID::\([0-9A-Za-z_]\+\)]], " [[" .. current_file .. "#\\1]]", "g")
	-- 7) Remove " | pg::N" where N is any integer.
	zorg_note_copy = vim.fn.substitute(zorg_note_copy, [[\v \| pg::\d+]], "", "g")
	return zorg_note_copy
end

--- Copies the current line as a Zorg note to the clipboard.
---
--- This function retrieves the current line, extracts the Zorg note content,
--- and copies it to the system clipboard with a newline character appended.
local function zorg_copy_note()
	local line = vim.fn.getline(".")
	local zorg_note_copy = get_zorg_note_copy(line)
	bb.copy_to_clipboard(zorg_note_copy .. "\n")
end

--- Copies a Zorg note + reference with an optional tag
---
---@param should_append? boolean Whether to append the text to the clipboard.
---@param tag? string A zorg tag to append to the reference note.
local function zorg_copy_note_ref(should_append, tag)
	local tag_space = ""
	if tag ~= nil then
		tag_space = tag .. " "
	end

	local line = vim.fn.getline(".")
	local zid_link = "[" .. get_zorg_note_zid(line) .. "]"
	local zorg_note_copy = get_zorg_note_copy(line)

	-- Perform a Vim regex substitution to remove leading markers like `[ox\-<>] (P[0-9] )?`
	local zorg_note_ref = vim.fn.substitute(zorg_note_copy, [[\v[ox\-<>] (P[0-9] )?]], "- " .. tag_space, "")

	-- Append " | [ZID]"
	zorg_note_ref = zorg_note_ref .. " | " .. zid_link

	bb.copy_to_clipboard(zorg_note_ref .. "\n", should_append)
end

-- Expression map to interpret forward slash, which triggers file-name completion.
vim.keymap.set("i", "/", function()
	return interpret_forward_slash()
end, { expr = true })

-- Maps to copy text to clipboard based on the Zorg note on the current line.
vim.keymap.set("n", "<localleader>c", zorg_copy_note, { desc = "Copy note (zettel) to clipboard." })
vim.keymap.set("n", "<localleader>z", zorg_copy_note_ref, { desc = "Copy reference to note (zettel) to clipboard." })
vim.keymap.set("n", "<localleader>Z", function()
	zorg_copy_note_ref(true)
	vim.fn["repeat#set"](vim.api.nvim_replace_termcodes("<localleader>Z", true, true, true))
end, { desc = "Append reference to note (zettel) to clipboard." })

vim.api.nvim_create_autocmd("BufWinEnter", {
	pattern = "*.zoq",
	callback = function()
		vim.cmd("normal mmgg")
		run_open_zorg_action(0)
		vim.cmd("normal `m")
	end,
})

-- AUTOCMD: Keymaps to search for pomodoro notes in YYYY/*.zo files.
vim.api.nvim_create_autocmd("BufEnter", {
	pattern = "20[0-9][0-9][0-9][0-9][0-9][0-9]_\\(day\\|poms\\).zo",
	callback = function()
		-- KEYMAP(N): <localleader><localleader>
		vim.keymap.set(
			"n",
			"<localleader><localleader>",
			":call SearchCurrentPomodoro()<cr>",
			{ buffer = true, desc = "Search for the currently active [[pomodoro]] note." }
		)
		-- KEYMAP(N): <localleader>|
		vim.keymap.set(
			"n",
			"<localleader>|",
			":call SearchNextPomodoro()<cr>",
			{ buffer = true, desc = "Search for the next unstarted [[pomodoro]] note." }
		)
	end,
})

--- Increments start/end times in HHMM format by a specified number of minutes.
--- Searches for the first line in the file matching the pattern.
---
---@param minutes number The number of minutes to add to both start and end times.
local function increment_start_end_times(minutes)
	-- Search for the first line matching the pattern
	local pattern = [[\vstart::\d\d\d\d\s+end::\d\d\d\d]]
	local line_num = vim.fn.search(pattern, "w")

	if line_num == 0 then
		print("No start::HHMM end::HHMM pattern found in file")
		return
	end

	local line = vim.fn.getline(line_num)
	local start_time, end_time = line:match("start::(%d%d%d%d)%s+end::(%d%d%d%d)")

	if not start_time or not end_time then
		print("No start::HHMM end::HHMM pattern found")
		return
	end

	--- Adds minutes to a time string in HHMM format
	---@param time_str string Time in HHMM format
	---@param mins number Minutes to add
	---@return string # New time in HHMM format
	local function add_minutes(time_str, mins)
		local hours = tonumber(time_str:sub(1, 2))
		local mins_part = tonumber(time_str:sub(3, 4))

		local total_mins = hours * 60 + mins_part + mins
		local new_hours = math.floor(total_mins / 60) % 24
		local new_mins = total_mins % 60

		return string.format("%02d%02d", new_hours, new_mins)
	end

	local new_start = add_minutes(start_time, minutes)
	local new_end = add_minutes(end_time, minutes)

	-- Replace the times in the line
	local new_line = line:gsub("start::" .. start_time, "start::" .. new_start)
	new_line = new_line:gsub("end::" .. end_time, "end::" .. new_end)

	vim.fn.setline(line_num, new_line)
end

-- KEYMAP(N): <localleader>o
vim.keymap.set("n", "<localleader>o", function()
	local count = vim.v.count1 -- Default to 1 if no count provided
	increment_start_end_times(count * 5)
end, { desc = "Increment start/end times by 5 minutes (accepts count multiplier)" })

-- KEYMAP(N): <localleader>O
vim.keymap.set("n", "<localleader>O", function()
	local count = vim.v.count1 -- Default to 1 if no count provided
	increment_start_end_times(-count * 5)
end, { desc = "Decrement start/end times by 5 minutes (accepts count multiplier)" })

-- KEYMAP(I): [i
vim.keymap.set("i", "[i", function()
	delete_dot_zo_before_cursor()
	vim.cmd([[
	     normal mavi["py
	     execute 'silent !zo_get_property -F ' . getreg('p') . ' LID > ~/org/.index'
	     normal `a
	     redraw!
       call feedkeys("#\<C-x>\<C-u>\<C-p>", 'n')
	   ]])
end)
