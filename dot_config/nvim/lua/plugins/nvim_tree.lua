-- P0: Fix \n keymap so it can deactivate the tree again!
-- P1: Remap 'g?' to '?' and sort by description by default!
-- P3: Create zorg notes for best 'nvim-tree' keymaps!
return {
	"nvim-tree/nvim-tree.lua",
	init = function()
		require("nvim-tree").setup({})
		vim.keymap.set("n", "<localleader>n", function()
			vim.cmd(string.format("wincmd o | NvimTreeToggle %s", vim.fn.expand("%:h")))
		end)
	end,
}
