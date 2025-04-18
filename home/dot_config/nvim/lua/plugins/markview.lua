--- A hackable markdown, Typst, latex, html(inline) & YAML previewer for Neovim.

return {
	-- PLUGIN: http://github.com/OXY2DEV/markview.nvim
	{
		"OXY2DEV/markview.nvim",
		lazy = false,
		ft = { "Avante", "markdown", "octo" },
		opts = {
			preview = {
				filetypes = { "Avante", "markdown", "octo" },
				ignore_buftypes = {},
			},
		},
		init = function()
			-- KEYMAP: <leader>M
			vim.keymap.set("n", "<leader>M", "<cmd>Markview toggle<cr>", { desc = "Markview toggle" })
		end,
	},
}
