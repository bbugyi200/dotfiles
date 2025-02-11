--- Keymaps that make buffer navigation easier live here.
---
--- Namely, this module defines the following keymaps:
---
--- <dash>       : Switch to buffer.
--- <underscore> : Horizontal split buffer.
--- <pipe>       : Vertical split buffer.
--- <plus>       : Tab split buffer.

--- Helper function to get the first existing listed buffer
--- (i.e. the buffer with the smallest number in the "listed" set)
---
---@return integer # The buffer number of the first existing buffer.
local function first_listed_buffer()
	local listed = vim.fn.getbufinfo({ buflisted = 1 })
	if #listed == 0 then
		-- Fallback: if no listed buffers exist (edge case), just return 1
		return 1
	end
	-- Sort by buffer number and return the smallest
	table.sort(listed, function(a, b)
		return a.bufnr < b.bufnr
	end)
	return listed[1].bufnr
end

-- KEYMAP(N): -
vim.keymap.set("n", "-", function()
	local count = vim.v.count
	if count == 0 then
		count = first_listed_buffer()
	end
	vim.cmd("buffer " .. count)
end, { desc = "Switch to buffer" })

-- KEYMAP(N): _
vim.keymap.set("n", "_", function()
	local count = vim.v.count
	if count == 0 then
		-- If no count provided, use the current buffer number
		count = vim.fn.bufnr("%")
	end
	vim.cmd("sbuffer " .. count)
end, { desc = "Horizontal split buffer" })

-- KEYMAP(N): |
vim.keymap.set("n", "|", function()
	local count = vim.v.count
	if count == 0 then
		count = vim.fn.bufnr("%")
	end
	vim.cmd("vert sbuffer " .. count)
end, { desc = "Vertical split buffer" })

-- KEYMAP(N): +
vim.keymap.set("n", "+", function()
	local count = vim.v.count
	local orig_buff_num = vim.fn.bufnr("%")
	if count == 0 then
		count = vim.fn.bufnr("%")
	else
		-- HACK: I think this is maybe necessary because of the http://github.com/tiagovla/scope.nvim
		vim.cmd("buffer " .. count)
	end
	vim.cmd("tab sbuffer " .. count)
	-- The buffer that was focused before using this keymap should be the same
	-- one that is focused after using it!
	--
	-- NOTE: Related to the HACK described above.
	if count ~= orig_buff_num then
		vim.cmd("tabprev")
		vim.cmd("buffer " .. orig_buff_num)
		vim.cmd("tabnext")
	end
end, { desc = "Tab split buffer" })
