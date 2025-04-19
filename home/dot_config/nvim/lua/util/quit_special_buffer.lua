local M = {}

--- Quits a "fake buffer" (e.g. a help window or quickfix window).
---
---@param close_window_if_multiple? boolean Whether to close the window if there are multiple windows.
function M.quit_special_buffer(close_window_if_multiple)
	local altfile = vim.fn.expand("%")
	local listed_buffers = vim.fn.getbufinfo({ buflisted = 1 })
	if altfile ~= "" and vim.fn.filereadable(altfile) then
		vim.cmd("b#")
		-- HACK: Run 'edit' to reload the buffer, which fixes some highlighting
		-- issues at times. Check if the buffer is changed first to avoid "No
		-- write since last change" error.
		if vim.fn.getbufinfo(vim.fn.bufname())[1].changed ~= 1 then
			vim.cmd("edit")
		end
	elseif #listed_buffers > 1 then
		vim.cmd("bd")
	else
		vim.cmd("q")
	end

	if close_window_if_multiple and #vim.api.nvim_list_wins() > 1 then
		vim.cmd("wincmd c")
	end
end

return M
