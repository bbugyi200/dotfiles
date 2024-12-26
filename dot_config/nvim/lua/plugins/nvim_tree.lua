return {
	"nvim-tree/nvim-tree.lua",
	init = function()
		require("nvim-tree").setup({})
		vim.keymap.set("n", "<LocalLeader>n", ":NvimTreeToggle<cr>")
	end,
}
