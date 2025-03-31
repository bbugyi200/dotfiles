--- (Neo)Vim plugin for automatically highlighting other uses of the word under
--- the cursor using either LSP, Tree-sitter, or regex matching.

-- PLUGIN: http://github.com/RRethy/vim-illuminate
return {
	{
		"RRethy/vim-illuminate",
		init = function()
			vim.cmd([[
        hi IlluminatedWordText guifg=none guibg=none gui=standout,bold
        hi IlluminatedWordRead guifg=none guibg=none gui=standout,bold
        hi IlluminatedWordWrite guifg=none guibg=none gui=standout,bold
    ]])
		end,
	},
}
