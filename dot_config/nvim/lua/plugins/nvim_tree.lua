-- P0: Remap 'g?' to '?' and sort by description by default!
-- P1: Create zorg notes for best 'nvim-tree' keymaps!
return {
	"nvim-tree/nvim-tree.lua",
	init = function()
		require("nvim-tree").setup({})
		vim.keymap.set("n", "<localleader>n", function()
			vim.cmd("NvimTreeToggle " .. vim.fn.expand("%:h"))
		end)
	end,
}
