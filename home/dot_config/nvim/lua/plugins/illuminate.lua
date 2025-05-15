--- (Neo)Vim plugin for automatically highlighting other uses of the word under
--- the cursor using either LSP, Tree-sitter, or regex matching.

-- PLUGIN: http://github.com/RRethy/vim-illuminate
return {
	{
		"RRethy/vim-illuminate",
		init = function()
			vim.cmd([[
      augroup illuminate_augroup
        autocmd!
        autocmd VimEnter,ColorScheme * hi IlluminatedWordText guifg=none guibg=none gui=standout,bold
        autocmd VimEnter,ColorScheme * hi IlluminatedWordRead guifg=none guibg=none gui=standout,bold
        autocmd VimEnter,ColorScheme * hi IlluminatedWordWrite guifg=none guibg=none gui=standout,bold
      augroup END
    ]])
		end,
	},
}
