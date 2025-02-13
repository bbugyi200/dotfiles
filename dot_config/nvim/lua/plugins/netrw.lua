--- It's not because we use netrw that we cannot have nice things!

return {
	-- PLUGIN: http://github.com/prichrd/netrw.nvim
	{
		"prichrd/netrw.nvim",
		dependencies = { "nvim-tree/nvim-web-devicons" },
		opts = {},
		init = function()
			-- This prevents netrw from being set as the alternate file.
			--
			-- For more info: https://github.com/tpope/vim-vinegar/issues/25
			vim.g.netrw_altfile = 1
		end,
	},
}
