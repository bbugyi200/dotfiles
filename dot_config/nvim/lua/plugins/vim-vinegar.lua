--- vinegar.vim: Combine with netrw to create a delicious salad dressing

return {
	-- PLUGIN: http://github.com/tpope/vim-vinegar
	{
		"tpope/vim-vinegar",
		init = function()
			-- Re-enable netrw banner, since I can't really think of a benefit to disabling it.
			vim.g.netrw_banner = 1
		end,
	},
}
