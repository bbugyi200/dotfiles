--- Command-line abbrevations and custom user commands live here.
--
-- P1: Write util/*.lua function for abbreviations!

-- KEYMAP(C): %% (Expand %% to <dir>/)
vim.cmd("cnoremap <expr> %% getcmdtype() == ':' ? expand('%:h').'/' : '%%'")

-- KEYMAP(ABBREVIATION): :// --> :e <dir>/
vim.cmd("cnoreabbrev / <c-r>=getcmdpos() == 1 && getcmdtype() == ':' ? 'e ' . expand('%:h') : '/'<CR>")

-- KEYMAP(C): :h --> :help
vim.cmd("cnoreabbrev h <c-r>=getcmdpos() == 1 && getcmdtype() == ':' ? 'vert help' : 'h'<CR>")
vim.cmd("cnoreabbrev H <c-r>=getcmdpos() == 1 && getcmdtype() == ':' ? 'Help' : 'H'<CR>")
vim.api.nvim_create_user_command("Help", "help <args> | wincmd w | wincmd c", {
	desc = "Wrapper for :help that takes over current buffer (instead of splitting).",
	nargs = 1,
	complete = "help",
})

-- KEYMAP(C): :o --> :Explore
vim.cmd("cnoreabbrev o <c-r>=getcmdpos() == 1 && getcmdtype() == ':' ? 'Explore' : 'o'<CR>")

-- KEYMAP(C): :v --> :verbose
vim.cmd("cnoreabbrev v <c-r>=getcmdpos() == 1 && getcmdtype() == ':' ? 'verbose' : 'v'<CR>")
