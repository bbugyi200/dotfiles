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
		--
		-- P4: Add KEYMAP comments + descriptions (desc)!
		vim.api.nvim_set_keymap("n", "<Leader>xw", "<cmd>Trouble<cr>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xd", "<cmd>Trouble filter.buf=0<cr>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xl", "<cmd>Trouble loclist<cr>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap(
			"n",
			"<Leader>xq",
			"<cmd>cclose<cr><cmd>Trouble quickfix<cr>",
			{ silent = true, noremap = true }
		)
	end,
}
