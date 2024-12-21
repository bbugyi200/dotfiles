return {
	"preservim/nerdtree",
	init = function()
		vim.g.NERDTreeWinSize = 60
		vim.g.NERDTreeCustomOpenArgs =
			{ file = { reuse = "all", where = "p", keepopen = 0 }, dir = {} }
	end,
	keys = {
		{
			"<LocalLeader>n",
			":NERDTree <C-R>=escape(expand(\"%:p:h\"), '#')<CR><CR>",
			desc = "Load NerdTree window for current dir",
		},
		{
			"<LocalLeader>N",
			"NERDTreeToggle<cr>",
			desc = "Toggle NerdTree window",
		},
	},
}
