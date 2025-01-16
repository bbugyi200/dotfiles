return {
	"nvim-tree/nvim-tree.lua",
	init = function()
		require("nvim-tree").setup({})
		vim.keymap.set("n", "<localleader>n", function()
			vim.cmd("NvimTreeToggle " .. vim.fn.expand("%:h"))
		end)
	end,
}
