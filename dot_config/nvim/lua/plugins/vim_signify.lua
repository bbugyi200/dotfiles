return {
	-- PLUGIN: http://github.com/mhinz/vim-signify
	{
		"mhinz/vim-signify",
		init = function()
			vim.opt.signcolumn = "yes"
			vim.g.signify_skip_filename_pattern = { "\\.pipertmp.*" }
		end,
	},
}
