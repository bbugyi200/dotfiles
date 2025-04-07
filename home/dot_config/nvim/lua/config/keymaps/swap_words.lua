--- Keymaps for swapping words live here:
---
--- * ,xw: Swap the current word with the next word.
--- * ,xW: Swap the current word with the previous word.

-- KEYMAP GROUP: <leader>x
vim.keymap.set("n", "<leader>x", "<nop>", { desc = "Swap Stuff" })

-- KEYMAP: <leader>xw
vim.keymap.set("n", "<leader>xw", function()
	-- Store current word
	local current_word = vim.fn.expand("<cword>")
	vim.cmd('normal! "_yiw')

	-- Perform the swap using substitute
	vim.cmd([[silent! s/\(\%#\w\+\)\(\_W\+\)\(\w\+\)/\3\2\1/]])

	-- Clear search highlighting and find the swapped word
	vim.cmd("nohlsearch")
	vim.fn.search("\\V\\<" .. vim.fn.escape(current_word, "\\") .. "\\>")

	-- Make repeatable
	vim.fn["repeat#set"](vim.api.nvim_replace_termcodes("<leader>xw", true, true, true))
end, { desc = "Swap the current word with next word.", silent = true })

-- KEYMAP: <leader>xW
vim.keymap.set("n", "<leader>xW", function()
	-- Store current word
	local current_word = vim.fn.expand("<cword>")
	vim.cmd('normal! "_yiw')

	-- Search backwards for a word boundary
	local ok = pcall(function()
		vim.fn.search("\\w\\+\\_W\\+\\%#", "b")
	end)

	if ok then
		-- Perform the swap using substitute
		vim.cmd([[silent! s/\(\%#\w\+\)\(\_W\+\)\(\w\+\)/\3\2\1/]])

		-- Clear search highlighting
		vim.cmd("nohlsearch")

		-- Move cursor to swapped the word
		vim.fn.search("\\V\\<" .. vim.fn.escape(current_word, "\\") .. "\\>")

		-- Make repeatable
		vim.fn["repeat#set"](vim.api.nvim_replace_termcodes("<leader>xW", true, true, true))
	end
end, { desc = "Swap the current word with previous word.", silent = true })
