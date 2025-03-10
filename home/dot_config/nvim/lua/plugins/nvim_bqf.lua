--- Better quickfix window in Neovim, polish old quickfix window.

return {
	-- PLUGIN: http://github.com/kevinhwang91/nvim-bqf
	{
		"kevinhwang91/nvim-bqf",
		dependencies = { "junegunn/fzf", build = ":call fzf#install()" },
		ft = "qf",
		opts = {},
	},
}
