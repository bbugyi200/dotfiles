--- Keymaps related to LSP.

--- Used to produce repeatable keymaps to jumpt to the next/previous diagnostic.
---
---@return function, function # The appropriate goto_next() and goto_prev() functions.
local function get_goto_diags()
	local repeat_move = require("nvim-treesitter.textobjects.repeatable_move")
	return repeat_move.make_repeatable_move_pair(vim.diagnostic.goto_next, vim.diagnostic.goto_prev)
end

-- Unmap builtin keymaps that would slow down the 'gr' keymap defined in this file.
local gr_keymaps_to_unmap = { "gra", "gri", "grn", "grr" }
for _, lhs in ipairs(gr_keymaps_to_unmap) do
	if vim.fn.maparg(lhs, "n") ~= "" then
		vim.keymap.del("n", lhs)
	end
	if vim.fn.maparg(lhs, "x") ~= "" then
		vim.keymap.del("x", lhs)
	end
end

-- KEYMAP GROUP: <leader>ls
vim.keymap.set("n", "<leader>ls", "<nop>", { desc = "LSP" })

-- KEYMAP: <leader>lsr
vim.keymap.set("n", "<leader>lsr", "<cmd>lua vim.lsp.buf.rename()<CR>", {
	desc = "[LSP] Rename symbol under cursor.",
})

-- KEYMAP: <leader>lsa
vim.keymap.set(
	"n",
	"<leader>lsa",
	"<cmd>lua vim.lsp.buf.code_action()<CR>",
	{ desc = "[LSP] Get code actions for the current line." }
)

-- KEYMAP: K
vim.keymap.set("n", "K", "<cmd>lua vim.lsp.buf.hover()<CR>", {
	desc = "Show hover information",
})

-- KEYMAP: g0
vim.keymap.set("n", "g0", "<cmd>lua vim.lsp.buf.document_symbol()<CR>", {
	desc = "List document symbols",
})

-- KEYMAP: gW
vim.keymap.set("n", "gW", "<cmd>lua vim.lsp.buf.workspace_symbol()<CR>", {
	desc = "List workspace symbols",
})

-- KEYMAP: gd
vim.keymap.set("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>", {
	desc = "Go to definition",
})

-- KEYMAP: gD
vim.keymap.set("n", "gD", "<cmd>lua vim.lsp.buf.declaration()<CR>", {
	desc = "Go to declaration",
})

-- KEYMAP: gi
vim.keymap.set("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", {
	desc = "Go to implementation",
})

-- KEYMAP: gr
vim.keymap.set("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", {
	desc = "List references",
})

-- KEYMAP: <C-k>
vim.keymap.set("n", "<C-k>", "<cmd>lua vim.lsp.buf.signature_help()<CR>", {
	desc = "Show signature help",
})

-- KEYMAP: gy
vim.keymap.set("n", "gy", "<cmd>lua vim.lsp.buf.type_definition()<CR>", {
	desc = "Go to type definition",
})

-- KEYMAP: [d
vim.keymap.set("n", "[d", function()
	local _, goto_prev = get_goto_diags()
	goto_prev()
end, { desc = "Go to previous diagnostic" })

-- KEYMAP: ]d
vim.keymap.set("n", "]d", function()
	local goto_next, _ = get_goto_diags()
	goto_next()
end, { desc = "Go to next diagnostic" })
