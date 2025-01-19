-- P1: Implement y* maps that copy parts of filename.
-- P2: Prefix every keymap command with a KEYMAP comment!
-- P2: Add fugitive keymaps!

--- Command-line maps / abhreviations.
--
-- Expand %% to current buffer's parent directory.
vim.cmd("cnoremap <expr> %% getcmdtype() == ':' ? expand('%:h').'/' : '%%'")

-- Allow semilcolon (;) to be treated the same as colon (:).
vim.keymap.set({ "n", "v" }, ";", ":")

-- Maps to save / exit.
vim.keymap.set({ "n", "i" }, "<leader>e", "<esc>:x!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>E", "<esc>:xa!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>s", "<esc>:update<cr>")

-- Maps that make buffer navigation easier.
--
-- P1: Fix BROKEN '+' map?!
-- P1: Change '-', '|', '_', and '+' map defaults to lowest buffer num (NOT 1).
vim.keymap.set("n", "_", ':<C-u>execute "sbuffer " . v:count1<CR>')
vim.keymap.set("n", "|", ':<C-u>execute "vert sbuffer " . v:count1<CR>')
vim.keymap.set("n", "+", ':<C-u>execute "tab sbuffer " . v:count<CR>')
vim.keymap.set("n", "-", ':<C-u>execute "buffer " . v:count1<CR>')

-- Maps that help you navigate files.
vim.keymap.set("n", "<C-\\>", "<C-^>")

-- Visual map to go to end-of-line.
vim.keymap.set("v", "<space>", "$<left>")

-- Configure LSP maps.
local lsp_opts = { noremap = true, silent = true }
vim.keymap.set("n", "<leader>rn", "<cmd>lua vim.lsp.buf.rename()<CR>", lsp_opts)
vim.keymap.set("n", "<leader>ca", "<cmd>lua vim.lsp.buf.code_action()<CR>", lsp_opts)
vim.keymap.set("n", "K", "<cmd>lua vim.lsp.buf.hover()<CR>", lsp_opts)
vim.keymap.set("n", "g0", "<cmd>lua vim.lsp.buf.document_symbol()<CR>", lsp_opts)
vim.keymap.set("n", "gW", "<cmd>lua vim.lsp.buf.workspace_symbol()<CR>", lsp_opts)
vim.keymap.set("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>", lsp_opts)
vim.keymap.set("n", "gD", "<cmd>lua vim.lsp.buf.declaration()<CR>", lsp_opts)
vim.keymap.set("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", lsp_opts)
vim.keymap.set("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", lsp_opts)
vim.keymap.set("n", "<C-k>", "<cmd>lua vim.lsp.buf.signature_help()<CR>", lsp_opts)
vim.keymap.set("n", "gt", "<cmd>lua vim.lsp.buf.type_definition()<CR>", lsp_opts)
vim.keymap.set("n", "[d", "<cmd>lua vim.diagnostic.goto_prev()<CR>", lsp_opts)
vim.keymap.set("n", "]d", "<cmd>lua vim.diagnostic.goto_next()<CR>", lsp_opts)

-- Map to search for a <WORD>.
vim.keymap.set("n", "<leader>/", "/\\v\\C<><Left>")

-- Maps to remove the current buffer.
local kill_buffer = require("util.kill_buffer").kill_buffer
vim.keymap.set("n", "<leader>dd", function()
	kill_buffer("#")
end)
vim.keymap.set("n", "<leader>dn", function()
	kill_buffer("next")
end)
vim.keymap.set("n", "<leader>dp", function()
	kill_buffer("prev")
end)

-- Swap with previous word ([w)
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
end, { silent = true })

-- Swap with next word (]w)
vim.keymap.set("n", "]w", function()
	-- Store current word
	local current_word = vim.fn.expand("<cword>")
	vim.cmd('normal! "_yiw')

	-- Perform the swap using substitute
	vim.cmd([[silent! s/\(\%#\w\+\)\(\_W\+\)\(\w\+\)/\3\2\1/]])

	-- Clear search highlighting and find the swapped word
	vim.cmd("nohlsearch")
	vim.fn.search("\\V\\<" .. vim.fn.escape(current_word, "\\") .. "\\>")
end, { silent = true })

-- Map to select the entire contents of the current file.
vim.keymap.set("n", "gV", "ggVG", { desc = "Map to select the entire contents of the current file." })

-- Map to insert space before and after character under cursor.
vim.keymap.set(
	"n",
	"<leader><space>",
	"a<Space><Esc>hi<Space><Esc>l",
	{ desc = "Map to insert space before and after character under cursor." }
)

-- Map to visually select next N lines (N defaults to 1 or v:count).
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
