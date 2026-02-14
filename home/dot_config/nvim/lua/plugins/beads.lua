return {
	-- PLUGIN: http://github.com/joeblubaugh/nvim-beads
	{
		"joeblubaugh/nvim-beads",
		config = function()
			require("beads").setup()
		end,
	},
}
