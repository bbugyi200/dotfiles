--- Keymaps related to LSP.

--- Used to produce repeatable keymaps to jumpt to the next/previous diagnostic.
---
---@return function, function # The appropriate goto_next() and goto_prev() functions.
local function get_goto_diags()
	local repeat_move = require("nvim-treesitter.textobjects.repeatable_move")
	return repeat_move.make_repeatable_move_pair(vim.diagnostic.goto_next, vim.diagnostic.goto_prev)
end

-- KEYMAP GROUP: <leader>ls
vim.keymap.set("n", "<leader>ls", "<nop>", { desc = "LSP" })

-- P2: Add KEYMAP comments to LSP keymaps!
vim.keymap.set("n", "<leader>lsr", "<cmd>lua vim.lsp.buf.rename()<CR>", {
	desc = "[LSP] Rename symbol under cursor.",
})
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
vim.keymap.set("n", "[d", function()
	local _, goto_prev = get_goto_diags()
	goto_prev()
end)
vim.keymap.set("n", "]d", function()
	local goto_next, _ = get_goto_diags()
	goto_next()
end)
