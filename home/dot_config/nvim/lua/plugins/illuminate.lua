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
          autocmd VimEnter,ColorScheme * hi! link IlluminatedWordText Visual
          autocmd VimEnter,ColorScheme * hi IlluminatedWordText gui=standout,bold
          autocmd VimEnter,ColorScheme * hi! link IlluminatedWordRead Visual
          autocmd VimEnter,ColorScheme * hi IlluminatedWordRead gui=standout,bold
          autocmd VimEnter,ColorScheme * hi! link IlluminatedWordWrite Visual
          autocmd VimEnter,ColorScheme * hi IlluminatedWordWrite gui=standout,bold
    ]])
		end,
	},
}
