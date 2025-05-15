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
        autocmd VimEnter,ColorScheme * highlight! link IlluminatedWordText Visual
        autocmd VimEnter,ColorScheme * highlight! link IlluminatedWordRead Visual
        autocmd VimEnter,ColorScheme * highlight! link IlluminatedWordWrite Visual
      augroup END
    ]])
		end,
	},
}
