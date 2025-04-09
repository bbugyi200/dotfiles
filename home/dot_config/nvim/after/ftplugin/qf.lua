--- Filetype: qf

local quit_special_buffer = require("util.quit_special_buffer")

-- KEYMAP: q
vim.keymap.set("n", "q", function()
	quit_special_buffer(true)
end, {
	buffer = true,
	desc = "Close the quickfix / location list buffer.",
})
-- KEYMAP: Q
vim.keymap.set("n", "Q", function()
	-- If we are in the location list...
	if vim.fn.get(vim.fn.getloclist(0, { winid = 0 }), "winid", 0) ~= 0 then
		vim.cmd("lclose | Trouble loclist")
		-- Otherwise, we are in the quickfix list.
	else
		vim.cmd("cclose | Trouble quickfix")
	end
end, { buffer = true, desc = "Send the quickfix results to Trouble." })
