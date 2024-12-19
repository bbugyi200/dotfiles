return {
  "preservim/nerdtree",
  config = function()
    vim.g.NERDTreeWinSize = 60
    vim.keymap.set('n', '<LocalLeader>n', ":NERDTree <C-R>=escape(expand(\"%:p:h\"), '#')<CR><CR>")
    vim.keymap.set('n', '<LocalLeader>N', ':NERDTreeToggle<CR>')
  end,
}
