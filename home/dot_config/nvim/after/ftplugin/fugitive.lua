--- Filetype: fugitive

-- KEYMAP: q
vim.keymap.set("n", "q", vim.cmd.close, {
	buffer = true,
	desc = "Close the fugitive buffer.",
})
