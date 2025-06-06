--- A hackable markdown, Typst, latex, html(inline) & YAML previewer for Neovim.

return {
	-- PLUGIN: http://github.com/OXY2DEV/markview.nvim
	{
		"OXY2DEV/markview.nvim",
		lazy = false,
		ft = { "Avante", "bugged", "codecompanion", "markdown", "octo" },
		opts = {
			preview = {
				filetypes = { "Avante", "bugged", "codecompanion", "markdown", "octo" },
				ignore_buftypes = {},
			},
		},
		init = function()
			-- KEYMAP: <leader>M
			-- KEYMAP: <leader>mdv
			for _, lhs in ipairs({ "<leader>M", "<leader>mdv" }) do
				vim.keymap.set("n", lhs, "<cmd>Markview toggle<cr>", { desc = "Markview toggle" })
			end
		end,
	},
}
