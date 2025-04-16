--- Navigation-related keymaps for Zorg files.
---
--- This module provides functions and keymaps for navigating between related
--- Zorg files. It includes functionality for:
--- - Going to related files
--- - Replacing buffers with related files
--- - Splitting (horizontally OR vertically) windows to open related files

local search = require("zorg.util.search")
local run_open_zorg_action = require("zorg.util.run_open_zorg_action")

--- Navigates to a related file based on a specified key.
---
--- This function performs the following steps:
--- 1. Sets a mark at the current position.
--- 2. Searches for a line containing the specified key.
--- 3. Calculates the line number difference between the old and new positions.
--- 4. Returns to the original position.
--- 5. Runs an action to open the related Zorg file.
---
--- @param key string The key to search for in the file.
local function go_to_related_file(key)
	local upper_key = key:upper()
	vim.cmd("normal mm")
	local old_line_no = vim.fn.line(".")
	search("\\v^\\s*# *" .. upper_key .. " = ")
	local new_line_no = vim.fn.line(".")
	local line_no_diff = new_line_no - old_line_no
	vim.cmd("normal! `m")
	run_open_zorg_action(line_no_diff)
end

--- Replaces the current buffer with a related file based on the given key.
---
---@param key string The key used to determine the related file
local function replace_buffer_with_related_file(key)
	local orig_bufnr = vim.fn.winbufnr(0)
	go_to_related_file(key)
	vim.cmd("split")
	vim.cmd("buffer " .. orig_bufnr)
	vim.cmd("bdelete")
end

--- Split the window and navigate to a related file.
---
---@param key string The key representing the related file type to navigate to.
local function split_related_file(key)
	vim.cmd("split")
	go_to_related_file(key)
	vim.cmd("wincmd x")
end

--- Switch to the related file in the vertical split neighbor window.
---
---@param key string The key used to determine the related file type (e.g., 'a' for alternate, 't' for test)
local function switch_vert_split_neighbor_to_related_file(key)
	local orig_bufnr = vim.fn.winbufnr(0)
	vim.cmd("wincmd l")
	vim.cmd("buffer " .. orig_bufnr)
	go_to_related_file(key)
	vim.cmd("wincmd h")
end

--- Vertically splits the window and opens a related file.
---
--- If there's only one window, it creates a new vertical split and opens the related file.
--- If there are multiple windows, it switches the vertical split neighbor to the related file.
---
---@param key string The key representing the related file type
local function vert_split_related_file(key)
	if vim.fn.winnr("$") == 1 then
		vim.cmd("vsplit")
		go_to_related_file(key)
		vim.cmd("wincmd x")
	else
		switch_vert_split_neighbor_to_related_file(key)
	end
end

--- Maps keys for navigating related files.
---
---@param lower_key string The lowercase version of a related file's key.
---@param upper_key string The uppercase version of a related file's key.
local function set_keymap_group(lower_key, upper_key)
	vim.keymap.set("n", "=" .. lower_key, function()
		go_to_related_file(lower_key)
	end, { noremap = true, nowait = true, silent = true })
	vim.keymap.set("n", "=" .. upper_key, function()
		replace_buffer_with_related_file(lower_key)
	end, { noremap = true, nowait = true, silent = true })
	vim.keymap.set("n", "=\\" .. lower_key, function()
		vert_split_related_file(lower_key)
	end, { noremap = true, nowait = true, silent = true })
	vim.keymap.set("n", "=-" .. lower_key, function()
		split_related_file(lower_key)
	end, { noremap = true, nowait = true, silent = true })
end

--- Adds keymaps for navigating Zorg notes.
local function set_all_keymap_groups()
	vim.keymap.set("n", "=.", function()
		go_to_related_file("\\@")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "=>", function()
		replace_buffer_with_related_file("\\@")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "=\\.", function()
		vert_split_related_file("\\@")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "=-.", function()
		split_related_file("\\@")
	end, { noremap = true, nowait = true })

	vim.keymap.set("n", "= ", function()
		go_to_related_file("\\^")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "=\n", function()
		replace_buffer_with_related_file("\\^")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "=\\ ", function()
		vert_split_related_file("\\^")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "=- ", function()
		split_related_file("\\^")
	end, { noremap = true, nowait = true })

	vim.keymap.set("n", "[[", function()
		go_to_related_file("\\<")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "[{", function()
		replace_buffer_with_related_file("\\<")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "[\\", function()
		vert_split_related_file("\\<")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "[-", function()
		split_related_file("\\<")
	end, { noremap = true, nowait = true })

	vim.keymap.set("n", "]]", function()
		go_to_related_file("\\>")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "]}", function()
		replace_buffer_with_related_file("\\>")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "]\\", function()
		vert_split_related_file("\\>")
	end, { noremap = true, nowait = true })
	vim.keymap.set("n", "]-", function()
		split_related_file("\\>")
	end, { noremap = true, nowait = true })

	for _, pair in ipairs({
		{ "0", ")" },
		{ "1", "!" },
		{ "2", "@" },
		{ "3", "#" },
		{ "4", "$" },
		{ "5", "%" },
		{ "6", "^" },
		{ "7", "&" },
		{ "8", "*" },
		{ "9", "(" },
	}) do
		local num = pair[1]
		local symbol = pair[2]
		set_keymap_group(num, symbol)
	end

	for i = string.byte("a"), string.byte("z") do
		local lower_key = string.char(i)
		local upper_key = lower_key:upper()
		set_keymap_group(lower_key, upper_key)
	end

	vim.keymap.set("n", "<cr>", function()
		run_open_zorg_action(vim.v.count)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "<bs>", function()
		run_open_zorg_action(-vim.v.count1)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z0", function()
		run_open_zorg_action(vim.v.count, -1)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z)", function()
		run_open_zorg_action(-vim.v.count, -1)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z1", function()
		run_open_zorg_action(vim.v.count, 1)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z!", function()
		run_open_zorg_action(-vim.v.count, 1)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z2", function()
		run_open_zorg_action(vim.v.count, 2)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z@", function()
		run_open_zorg_action(-vim.v.count, 2)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z3", function()
		run_open_zorg_action(vim.v.count, 3)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z9", function()
		run_open_zorg_action(vim.v.count, 1)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z(", function()
		run_open_zorg_action(-vim.v.count, 1)
	end, { nowait = true, silent = true })
	vim.keymap.set("n", "z#", function()
		run_open_zorg_action(-vim.v.count, 3)
	end, { nowait = true, silent = true })
end

--- Sets hydra-mode keymaps to navigate Zorg files.
local function set_hydra_mode_keymaps()
	-- KEYMAP(N): <leader>=
	vim.keymap.set("n", "<leader>=", function()
		require("which-key").show({ keys = "=", loop = true })
	end, { desc = "Enable hydra-mode for '=' key." })
end

--- Configure all keymaps declared in this file.
local function set_all_keymaps()
	set_all_keymap_groups()
	set_hydra_mode_keymaps()
end

set_all_keymaps()
