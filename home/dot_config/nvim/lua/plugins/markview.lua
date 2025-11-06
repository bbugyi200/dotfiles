--- A hackable markdown, Typst, latex, html(inline) & YAML previewer for Neovim.

return {
	-- PLUGIN: http://github.com/OXY2DEV/markview.nvim
	{
		"OXY2DEV/markview.nvim",
		lazy = true,
		cmd = { "Markview" },
		opts = {
			preview = {
				filetypes = { "Avante", "bugged", "markdown", "octo" },
				ignore_buftypes = {},
			},
		},
		init = function()
			-- KEYMAP: <localleader>m
			vim.keymap.set("n", "<localleader>m", "<cmd>Markview toggle<cr>", { desc = "Markview toggle" })
		end,
	},
}
