-- P1: Configure a preview window for Trouble!
-- P2: Use [#trouble_nvim] for LSP references (e.g. for `gr` map)!
return {
	"folke/trouble.nvim",
	dependencies = {
		"nvim-tree/nvim-web-devicons",
	},
	opts = { focus = true, win = { size = 0.3 } },
	init = function()
		-- Mappings
		vim.api.nvim_set_keymap("n", "<Leader>xw", "<Cmd>Trouble<CR>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xd", "<Cmd>Trouble filter.buf=0<CR>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xl", "<Cmd>Trouble loclist<CR>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xq", "<Cmd>Trouble quickfix<CR>", { silent = true, noremap = true })
	end,
}
