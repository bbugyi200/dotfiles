-- LSP configuration lives here.

-- Enable virtual text and disable virtual lines by default.
vim.diagnostic.config({ virtual_lines = false, virtual_text = true })

-- ╭─────────────────────────────────────────────────────────╮
-- │                         KEYMAPS                         │
-- ╰─────────────────────────────────────────────────────────╯
-- KEYMAP: gI
vim.keymap.set("n", "gI", "<cmd>lua vim.lsp.buf.implementation()<cr>", {
	desc = "Goto implementation",
})
-- KEYMAP: K
vim.keymap.set("n", "K", vim.lsp.buf.hover, { desc = "Display preview of symbol's doc comment." })

-- ─────────────────────── <leader>ls KEYMAP GROUP ───────────────────────
-- KEYMAP GROUP: <leader>ls
vim.keymap.set("n", "<leader>ls", "<nop>", { desc = "LSP" })
-- KEYMAP: <leader>lsd
vim.keymap.set("n", "<leader>lsd", function()
	local virtual_lines = not vim.diagnostic.config().virtual_lines
	local virtual_text = not virtual_lines
	vim.diagnostic.config({ virtual_lines = virtual_lines, virtual_text = virtual_text })
	vim.notify(
		"Reconfigured virtual diagnostics: LINES=" .. tostring(virtual_lines) .. " TEXT=" .. tostring(virtual_text)
	)
end, { desc = "Toggle between diagnostics in virtual lines vs virtual text." })
