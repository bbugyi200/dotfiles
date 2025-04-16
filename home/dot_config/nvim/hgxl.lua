-- Used for 'hxx' commnd. INSPIRED BY: http://go/figtree

require("figtree").setup({
	ui = {
		size = { width = 1, height = 1 },
		border = "none",
	},
})
vim.api.nvim_create_autocmd("User", {
	pattern = "FigtreeClose",
	callback = function()
		vim.cmd("quit")
	end,
})
require("figtree").toggle()
