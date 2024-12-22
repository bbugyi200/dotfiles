-- Allow semilcolon (;) to be treated the same as colon (:).
vim.keymap.set({ "n", "v" }, ";", ":")

-- Maps to save / exit.
vim.keymap.set({ "n", "i" }, "<leader>e", ":x!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>E", ":xa!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>s", ":update<cr>")

-- Maps that make buffer navigation easier.
vim.keymap.set("n", "_", ':<C-u>execute "sbuffer " . v:count1<CR>')
vim.keymap.set("n", "|", ':<C-u>execute "vert sbuffer " . v:count1<CR>')
vim.keymap.set("n", "+", ':<C-u>execute "tab sbuffer " . v:count<CR>')
vim.keymap.set("n", "-", ':<C-u>execute "buffer " . v:count1<CR>')

-- Maps that help you navigate files.
vim.keymap.set("n", "<C-\\>", "<C-^>")
vim.keymap.set("n", "<space>", ":FzfLua buffers<cr>")

-- Visual map to go to end-of-line.
vim.keymap.set("v", "<space>", "$<left>")

-- Configure LSP keymaps
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
