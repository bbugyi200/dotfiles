--- Simple keymaps live here.
---
--- NOTE: Complicated keymaps (ex: ones that benefit from factoring out
--- functions) SHOULD be defined in a separate config/keymaps/*.lua file!

local copy_to_clipboard = require("util.copy_to_clipboard")

-- KEYMAP: w!!
vim.keymap.set(
	"c",
	"w!!",
	"w !sudo tee > /dev/null %",
	{ desc = "Save the current file with elevated (using sudo) permissions." }
)

-- KEYMAP: ;
vim.keymap.set({ "n", "v" }, ";", ":", { desc = "Map semicolon to colon." })

-- Maps to save / exit.
--
-- P2: Add KEYMAP comments to save/exit keymaps!
vim.keymap.set({ "n", "i" }, "<leader>e", "<esc>:x!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>E", "<esc>:xa!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>s", "<esc>:update<cr>")

-- KEYMAP: <C-\>
vim.keymap.set("n", "<C-\\>", "<C-^>", { desc = "Navigate to alternate file." })

-- KEYMAP: <space>
vim.keymap.set("v", "<space>", "$<left>", { desc = "Visual map to go to the end of the line." })

-- KEYMAP: <leader>/
vim.keymap.set("n", "<leader>/", "/\\v\\C<><Left>", { desc = "Map to search for a <WORD>." })

-- KEYMAP: <leader><space>
vim.keymap.set(
	"n",
	"<leader><space>",
	"a<Space><Esc>hi<Space><Esc>l",
	{ desc = "Map to insert space before and after character under cursor." }
)

-- KEYMAP: <leader>v
vim.keymap.set("n", "<leader>v", function()
	-- NOTE: We MUST store this count before calling `vim.cmd("normal V")`!
	local count
	if vim.v.count > 0 then
		count = vim.v.count
	else
		count = 1
	end
	vim.cmd("normal V" .. count .. "j")
end, { desc = "Map to visually select next N lines (N defaults to 1 or v:count)." })

-- KEYMAP: <leader>h
vim.keymap.set("n", "<leader>h", function()
	vim.cmd("nohlsearch")
	vim.cmd("redraw")
end, { silent = true, desc = "Disable search highlighting temporarily (until the next search)." })

-- KEYMAP: &
--
-- Used to preserve the flags of the last substitution.
vim.cmd("nnoremap & :&&<CR>")
vim.cmd("xnoremap & :&&<CR>")

-- KEYMAP: cd
vim.keymap.set("n", "cd", ":cd ", { desc = "Shortcut to make changing directories faster." })

-- Make j and k smarter about moving up and down virtual lines.
--
-- KEYMAP: j
vim.keymap.set("n", "j", "(v:count ? 'j' : 'gj')", { desc = "Go down one (virtual) line.", expr = true })
-- KEYMAP: k
vim.keymap.set("n", "k", "(v:count ? 'k' : 'gk')", { desc = "Go up one (virtual) line.", expr = true })

-- Resize windows using arrow keys!
--
-- KEYMAP: <up>
vim.keymap.set("n", "<up>", ":resize -2<cr>", { desc = "Resize window (UP)." })
-- KEYMAP: <down>
vim.keymap.set("n", "<down>", ":resize +2<cr>", { desc = "Resize window (DOWN)." })
-- KEYMAP: <left>
vim.keymap.set("n", "<left>", ":vertical resize -2<cr>", { desc = "Resize window (LEFT)." })
-- KEYMAP: <right>
vim.keymap.set("n", "<right>", ":vertical resize +2<cr>", { desc = "Resize window (RIGHT)." })

-- KEYMAP: <leader>co
vim.keymap.set("n", "<leader>co", function()
	local qf_exists = false
	for _, win in pairs(vim.fn.getwininfo()) do
		if win.quickfix == 1 then
			qf_exists = true
		end
	end
	if qf_exists == true then
		vim.cmd("cclose")
	else
		vim.cmd("copen")
	end
end, { desc = "Toggle visibility of the quickfix window." })

-- KEYMAP: <leader>lo
vim.keymap.set("n", "<leader>lo", function()
	local win = vim.fn.getloclist(0, { winid = 0 }).winid
	if win == 0 then
		vim.cmd("lopen")
	else
		vim.cmd("lclose")
	end
end, { desc = "Toggle visibility of the location list." })

-- KEYMAP: yY
vim.keymap.set("n", "yY", function()
	copy_to_clipboard(vim.fn.getline(".") .. "\n", true)
end, {
	desc = "Append the line under cursor to clipboard.",
})
