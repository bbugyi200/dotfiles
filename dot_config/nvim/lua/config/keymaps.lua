-- P2: Add fugitive keymaps!
-- P2: Implement y* maps that copy parts of filename.

local map = vim.keymap.set

---@alias BufferDirection
---| "#" The last active buffer.
---| "next" The next buffer.
---| "prev" The previous buffer.
---
--- Remove a buffer and navigate to another buffer specified via {direction}.
---
---@param direction BufferDirection A string indicating a relative buffer direction.
local function remove_buffer(direction)
	vim.cmd("b" .. direction .. " | sp | b# | bd")
end

-- Allow semilcolon (;) to be treated the same as colon (:).
map({ "n", "v" }, ";", ":")

-- Maps to save / exit.
map({ "n", "i" }, "<leader>e", "<esc>:x!<cr>")
map({ "n", "i" }, "<leader>E", "<esc>:xa!<cr>")
map({ "n", "i" }, "<leader>s", "<esc>:update<cr>")

-- Maps that make buffer navigation easier.
--
-- P1: Fix BROKEN '+' map?!
-- P1: Change '-', '|', '_', and '+' map defaults to lowest buffer num (NOT 1).
map("n", "_", ':<C-u>execute "sbuffer " . v:count1<CR>')
map("n", "|", ':<C-u>execute "vert sbuffer " . v:count1<CR>')
map("n", "+", ':<C-u>execute "tab sbuffer " . v:count<CR>')
map("n", "-", ':<C-u>execute "buffer " . v:count1<CR>')

-- Maps that help you navigate files.
map("n", "<C-\\>", "<C-^>")

-- Visual map to go to end-of-line.
map("v", "<space>", "$<left>")

-- Configure LSP maps.
local lsp_opts = { noremap = true, silent = true }
map("n", "<leader>rn", "<cmd>lua vim.lsp.buf.rename()<CR>", lsp_opts)
map("n", "<leader>ca", "<cmd>lua vim.lsp.buf.code_action()<CR>", lsp_opts)
map("n", "K", "<cmd>lua vim.lsp.buf.hover()<CR>", lsp_opts)
map("n", "g0", "<cmd>lua vim.lsp.buf.document_symbol()<CR>", lsp_opts)
map("n", "gW", "<cmd>lua vim.lsp.buf.workspace_symbol()<CR>", lsp_opts)
map("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>", lsp_opts)
map("n", "gD", "<cmd>lua vim.lsp.buf.declaration()<CR>", lsp_opts)
map("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", lsp_opts)
map("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", lsp_opts)
map("n", "<C-k>", "<cmd>lua vim.lsp.buf.signature_help()<CR>", lsp_opts)
map("n", "gt", "<cmd>lua vim.lsp.buf.type_definition()<CR>", lsp_opts)
map("n", "[d", "<cmd>lua vim.diagnostic.goto_prev()<CR>", lsp_opts)
map("n", "]d", "<cmd>lua vim.diagnostic.goto_next()<CR>", lsp_opts)

-- Map to search for a <WORD>.
map("n", "<leader>/", "/\\v\\C<><Left>")

-- Maps to remove the current buffer.
map("n", "<leader>dd", function()
	remove_buffer("#")
end)
map("n", "<leader>dn", function()
	remove_buffer("next")
end)
map("n", "<leader>dp", function()
	remove_buffer("prev")
end)

-- Map to make editing adjacent files easier
map("n", "<leader><leader>e", ':e <C-R>=expand("%:p:h") . "/" <CR>')

-- Swap with previous word ([w)
map("n", "[w", function()
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
map("n", "]w", function()
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
map("n", "gV", "ggVG", { desc = "Map to select the entire contents of the current file." })

-- Map to insert space before and after character under cursor.
map(
	"n",
	"<leader><space>",
	"a<Space><Esc>hi<Space><Esc>l",
	{ desc = "Map to insert space before and after character under cursor." }
)
