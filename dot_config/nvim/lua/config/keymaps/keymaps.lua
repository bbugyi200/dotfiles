--- Simple keymaps live here.
---
--- NOTE: Complicated keymaps (ex: ones that benefit from factoring out
--- functions) SHOULD be defined in a separate config/keymaps/*.lua file!
--
-- P1: Write util/*.lua function for abbreviations!

-- KEYMAP(C): w!!
vim.keymap.set(
	"c",
	"w!!",
	"w !sudo tee > /dev/null %",
	{ desc = "Save the current file with elevated (using sudo) permissions." }
)

-- KEYMAP(N+V): ;
vim.keymap.set({ "n", "v" }, ";", ":", { desc = "Map semicolon to colon." })

-- Maps to save / exit.
--
-- P2: Add KEYMAP comments to save/exit keymaps!
vim.keymap.set({ "n", "i" }, "<leader>e", "<esc>:x!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>E", "<esc>:xa!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>s", "<esc>:update<cr>")

-- KEYMAP(N): <C-\>
vim.keymap.set("n", "<C-\\>", "<C-^>", { desc = "Navigate to alternate file." })

-- KEYMAP(V): <space>
vim.keymap.set("v", "<space>", "$<left>", { desc = "Visual map to go to the end of the line." })

-- Configure LSP maps.
--
-- P2: Add KEYMAP comments to LSP keymaps!
vim.keymap.set("n", "<leader>ls", "<nop>", { desc = "LSP keymaps" })
vim.keymap.set("n", "<leader>lsr", "<cmd>lua vim.lsp.buf.rename()<CR>", { desc = "[LSP] Rename symbol under cursor." })
vim.keymap.set(
	"n",
	"<leader>lsa",
	"<cmd>lua vim.lsp.buf.code_action()<CR>",
	{ desc = "[LSP] Get code actions for the current line." }
)
vim.keymap.set("n", "K", "<cmd>lua vim.lsp.buf.hover()<CR>")
vim.keymap.set("n", "g0", "<cmd>lua vim.lsp.buf.document_symbol()<CR>")
vim.keymap.set("n", "gW", "<cmd>lua vim.lsp.buf.workspace_symbol()<CR>")
vim.keymap.set("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>")
vim.keymap.set("n", "gD", "<cmd>lua vim.lsp.buf.declaration()<CR>")
vim.keymap.set("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>")
vim.keymap.set("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>")
vim.keymap.set("n", "<C-k>", "<cmd>lua vim.lsp.buf.signature_help()<CR>")
vim.keymap.set("n", "gy", "<cmd>lua vim.lsp.buf.type_definition()<CR>")
vim.keymap.set("n", "[d", "<cmd>lua vim.diagnostic.goto_prev()<CR>")
vim.keymap.set("n", "]d", "<cmd>lua vim.diagnostic.goto_next()<CR>")

-- KEYMAP(N): <leader>/
vim.keymap.set("n", "<leader>/", "/\\v\\C<><Left>", { desc = "Map to search for a <WORD>." })

-- KEYMAP(N): [w
vim.keymap.set("n", "[w", function()
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
	end
end, { desc = "Swap the current word with previous word.", silent = true })

-- KEYMAP(N): ]w
vim.keymap.set("n", "]w", function()
	-- Store current word
	local current_word = vim.fn.expand("<cword>")
	vim.cmd('normal! "_yiw')

	-- Perform the swap using substitute
	vim.cmd([[silent! s/\(\%#\w\+\)\(\_W\+\)\(\w\+\)/\3\2\1/]])

	-- Clear search highlighting and find the swapped word
	vim.cmd("nohlsearch")
	vim.fn.search("\\V\\<" .. vim.fn.escape(current_word, "\\") .. "\\>")
end, { desc = "Swap the current word with next word.", silent = true })

-- KEYMAP(N): <leader><space>
vim.keymap.set(
	"n",
	"<leader><space>",
	"a<Space><Esc>hi<Space><Esc>l",
	{ desc = "Map to insert space before and after character under cursor." }
)

-- KEYMAP(N): <leader>v
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

-- KEYMAP(N): <c-l>
vim.keymap.set("n", "<C-l>", function()
	vim.cmd("nohlsearch")
	vim.cmd("redraw")
end, { silent = true, desc = "Disable search highlighting temporarily (until the next search)." })

-- KEYMAP(N+V): &
--
-- Used to preserve the flags of the last substitution.
vim.cmd("nnoremap & :&&<CR>")
vim.cmd("xnoremap & :&&<CR>")

-- KEYMAP(N): cd
vim.keymap.set("n", "cd", ":cd ", { desc = "Shortcut to make changing directories faster." })

-- Make j and k smarter about moving up and down virtual lines.
--
-- KEYMAP(N): j
vim.keymap.set("n", "j", "(v:count ? 'j' : 'gj')", { desc = "Go down one (virtual) line.", expr = true })
-- KEYMAP(N): k
vim.keymap.set("n", "k", "(v:count ? 'k' : 'gk')", { desc = "Go up one (virtual) line.", expr = true })

-- Resize windows using arrow keys!
--
-- KEYMAP(N): <up>
vim.keymap.set("n", "<up>", ":resize -2<cr>", { desc = "Resize window (UP)." })
-- KEYMAP(N): <down>
vim.keymap.set("n", "<down>", ":resize +2<cr>", { desc = "Resize window (DOWN)." })
-- KEYMAP(N): <left>
vim.keymap.set("n", "<left>", ":vertical resize -2<cr>", { desc = "Resize window (LEFT)." })
-- KEYMAP(N): <right>
vim.keymap.set("n", "<right>", ":vertical resize +2<cr>", { desc = "Resize window (RIGHT)." })

-- Remap ';' and ',' since I map ';' to ':' and ',' is my <leader> key.
--
-- KEYMAP(N+V): <localleader><localleader>
vim.keymap.set({ "n", "v" }, "<localleader><localleader>", ";", { desc = "Remap the ';' key." })
-- KEYMAP(+VN): <localleader>|
vim.keymap.set({ "n", "v" }, "<localleader>|", ",", { desc = "Remap the ',' key." })

-- KEYMAP(N): <leader>&
vim.keymap.set("n", "<leader>&", "<cmd>cfdo %s//~/&<cr>", {
	desc = "Re-run last :substitute command on all buffers in the quickfix list.",
})
