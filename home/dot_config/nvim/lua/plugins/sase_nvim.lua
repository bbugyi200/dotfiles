return {
	{
		"sase-org/sase-nvim",
		config = function()
			require("sase").setup({
				complete = { keymap = true },
			})
		end,
	},
}
