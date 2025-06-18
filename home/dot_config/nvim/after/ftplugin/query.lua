--- Filetype: query

local bb = require("bb_utils")

-- KEYMAP: q
vim.keymap.set("n", "q", function()
	bb.quit_special_buffer(true)
end, {
	buffer = true,
	desc = "Close the treesitter query buffer.",
})
