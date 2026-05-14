return {
	{
		"sase-org/sase-nvim",
		dir = "~/projects/github/sase-org/sase-nvim",
		config = function()
			require("sase").setup({
				complete = {
					keymap = true,
					completion_backend = "auto",
				},
				lsp = {
					enabled = true,
					native_completion = false,
				},
			})
		end,
	},
}
