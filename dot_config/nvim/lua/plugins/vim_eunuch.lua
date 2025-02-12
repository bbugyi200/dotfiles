--- vim-eunuch: Vim sugar for the UNIX shell commands that need it.

return {
	-- PLUGIN: http://github.com/tpope/vim-eunuch
	{
		"tpope/vim-eunuch",
		opts = {},
		init = function()
			vim.g.eunuch_interpreters = { bash = "/bin/bash" }
		end,
	},
}
