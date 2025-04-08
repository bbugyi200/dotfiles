--- Neovim plugin for silicon in Rust.

return {
	-- PLUGIN: http://github.com/krivahtoo/silicon.nvim
	{
		"krivahtoo/silicon.nvim",
		build = "./install.sh build",
		config = function()
			require("silicon").setup({
				font = "FantasqueSansMono Nerd Font=26",
				background = "#87f",
				theme = "Monokai Extended",
				line_number = true,
				pad_vert = 80,
				pad_horiz = 50,
				output = {
					path = vim.env.HOME .. "/org/img",
				},
				watermark = {
					text = " @bbugyi200",
				},
				window_title = function()
					return vim.fn.fnamemodify(vim.fn.bufname(vim.fn.bufnr()), ":~:.")
				end,
			})
		end,
	},
}
