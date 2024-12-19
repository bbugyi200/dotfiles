return {
  "sirver/ultisnips",
  "google/vim-searchindex",
  {
    "ap/vim-buftabline",
    config = function()
      vim.cmd([[
        let g:buftabline_numbers = 1
        let g:buftabline_indicators = 1
	hi BufTabLineCurrent ctermfg=black ctermbg=yellow cterm=bold,underline
      ]])
    end,
  },
  "tpope/vim-commentary",
  "tpope/vim-dispatch",
  "tpope/vim-fugitive",
  "tpope/vim-repeat",
  "tpope/vim-surround",
  "tpope/vim-unimpaired",
  "tpope/vim-vinegar",
  "tpope/vim-scriptease",
  "tpope/vim-abolish",
  "Raimondi/delimitMate",
  "mhinz/vim-startify",
}
