local funcs = require("funcs")
local keymap = vim.keymap.set

-- Allow semilcolon (;) to be treated the same as colon (:).
keymap({ "n", "v" }, ";", ":")

-- Maps to save / exit.
keymap({ "n", "i" }, "<leader>e", "<esc>:x!<cr>")
keymap({ "n", "i" }, "<leader>E", "<esc>:xa!<cr>")
keymap({ "n", "i" }, "<leader>s", "<esc>:update<cr>")

-- Maps that make buffer navigation easier.
keymap("n", "_", ':<C-u>execute "sbuffer " . v:count1<CR>')
keymap("n", "|", ':<C-u>execute "vert sbuffer " . v:count1<CR>')
keymap("n", "+", ':<C-u>execute "tab sbuffer " . v:count<CR>')
keymap("n", "-", ':<C-u>execute "buffer " . v:count1<CR>')

-- Maps that help you navigate files.
keymap("n", "<C-\\>", "<C-^>")
keymap("n", "<space>", ":FzfLua buffers<cr>")

-- Visual map to go to end-of-line.
keymap("v", "<space>", "$<left>")

-- Configure LSP keymaps.
local lsp_opts = { noremap = true, silent = true }
keymap("n", "<leader>rn", "<cmd>lua vim.lsp.buf.rename()<CR>", lsp_opts)
keymap("n", "<leader>ca", "<cmd>lua vim.lsp.buf.code_action()<CR>", lsp_opts)
keymap("n", "K", "<cmd>lua vim.lsp.buf.hover()<CR>", lsp_opts)
keymap("n", "g0", "<cmd>lua vim.lsp.buf.document_symbol()<CR>", lsp_opts)
keymap("n", "gW", "<cmd>lua vim.lsp.buf.workspace_symbol()<CR>", lsp_opts)
keymap("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>", lsp_opts)
keymap("n", "gD", "<cmd>lua vim.lsp.buf.declaration()<CR>", lsp_opts)
keymap("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", lsp_opts)
keymap("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", lsp_opts)
keymap("n", "<C-k>", "<cmd>lua vim.lsp.buf.signature_help()<CR>", lsp_opts)
keymap("n", "gt", "<cmd>lua vim.lsp.buf.type_definition()<CR>", lsp_opts)
keymap("n", "[d", "<cmd>lua vim.diagnostic.goto_prev()<CR>", lsp_opts)
keymap("n", "]d", "<cmd>lua vim.diagnostic.goto_next()<CR>", lsp_opts)

-- Map to search for a <WORD>.
keymap("n", "<leader>/", "/\\v\\C<><Left>")

-- Maps to remove the current buffer.
keymap("n", "<leader>dd", function()
	funcs.remove_buffer("#")
end)
keymap("n", "<leader>dn", function()
	funcs.remove_buffer("n")
end)
keymap("n", "<leader>dp", function()
	funcs.remove_buffer("p")
end)

-- Map to make editing adjacent files easier
keymap("n", "<leader><leader>e", ':e <C-R>=expand("%:p:h") . "/" <CR>')

-- Swap with previous word ([w)
keymap("n", "[w", function()
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
keymap("n", "]w", function()
	-- Store current word
	local current_word = vim.fn.expand("<cword>")
	vim.cmd('normal! "_yiw')

	-- Perform the swap using substitute
	vim.cmd([[silent! s/\(\%#\w\+\)\(\_W\+\)\(\w\+\)/\3\2\1/]])

	-- Clear search highlighting and find the swapped word
	vim.cmd("nohlsearch")
	vim.fn.search("\\V\\<" .. vim.fn.escape(current_word, "\\") .. "\\>")
end, { silent = true })
