return {
	{
		"sase-org/sase-nvim",
		config = function()
			require("sase").setup({
				complete = {
					keymap = true,
					completion_backend = "auto",
				},
				lsp = {
					enabled = true,
				},
			})
		end,
	},
}
