-- P2: Configure a preview window for Trouble!
-- P2: Use [#trouble_nvim] for LSP references (e.g. for `gr` map)!

return {
	-- PLUGIN: http://github.com/folke/trouble.nvim
	{
		"folke/trouble.nvim",
		dependencies = {
			"nvim-tree/nvim-web-devicons",
		},
		opts = { focus = true, win = { size = 0.3 } },
	},
}
