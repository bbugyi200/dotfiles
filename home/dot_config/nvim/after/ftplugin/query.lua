--- Filetype: query

-- KEYMAP: q
vim.keymap.set("n", "q", vim.cmd.close, {
	buffer = true,
	desc = "Close the treesitter query buffer.",
})
