return {
  "sirver/ultisnips",
  "google/vim-searchindex",
  {
    "ap/vim-buftabline",
    config = function()
      vim.g.buftabline_numbers = 1
      vim.g.buftabline_indicators = 1
      vim.cmd([[
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
  {
    "preservim/nerdtree",
    config = function()
      vim.g.NERDTreeWinSize = 60
      vim.keymap.set('n', '<LocalLeader>n', ":NERDTree <C-R>=escape(expand(\"%:p:h\"), '#')<CR><CR>")
      vim.keymap.set('n', '<LocalLeader>N', ':NERDTreeToggle<CR>')
    end,
  },
}
