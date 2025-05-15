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
          autocmd VimEnter,ColorScheme * highlight IlluminatedWordText guibg=#3a4b5c guifg=NONE gui=NONE cterm=NONE
          autocmd VimEnter,ColorScheme * highlight IlluminatedWordRead guibg=#3a4b5c guifg=NONE gui=NONE cterm=NONE
          autocmd VimEnter,ColorScheme * highlight IlluminatedWordWrite guibg=#3a4b5c guifg=NONE gui=NONE cterm=NONE
        augroup END
      ]])
		end,
	},
}
