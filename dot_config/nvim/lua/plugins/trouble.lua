-- P1: Increase Trouble window size!
return {
	"folke/trouble.nvim",
	dependencies = {
		"nvim-tree/nvim-web-devicons",
	},
	init = function()
		-- Diagnostics
		require("trouble").setup({
			-- Set any options here from https://github.com/folke/trouble.nvim?tab=readme-ov-file#%EF%B8%8F-configuration
		})

		-- Mappings
		vim.api.nvim_set_keymap("n", "<Leader>xw", "<Cmd>Trouble<CR>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xd", "<Cmd>Trouble filter.buf=0<CR>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xl", "<Cmd>Trouble loclist<CR>", { silent = true, noremap = true })
		vim.api.nvim_set_keymap("n", "<Leader>xq", "<Cmd>Trouble quickfix<CR>", { silent = true, noremap = true })
	end,
}
