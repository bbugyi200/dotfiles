--- vim match-up: even better %. Navigate and highlight matching words. Modern matchit and matchparen.

return {
	-- PLUGIN: http://github.com/andymass/vim-matchup
	{
		"andymass/vim-matchup",
		init = function()
			vim.g.matchup_matchparen_offscreen = { method = "popup" }
		end,
	},
}
