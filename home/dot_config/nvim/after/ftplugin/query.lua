--- Filetype: query

local quit_special_buffer = require("util.quit_special_buffer")

-- KEYMAP: q
vim.keymap.set("n", "q", function()
	quit_special_buffer(true)
end, {
	buffer = true,
	desc = "Close the treesitter query buffer.",
})
