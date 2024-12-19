return {
  "ap/vim-buftabline",
  init = function()
    vim.g.buftabline_numbers = 1
    vim.g.buftabline_indicators = 1
    vim.cmd([[
      hi BufTabLineCurrent ctermfg=black ctermbg=yellow cterm=bold,underline
    ]])
  end,
}
