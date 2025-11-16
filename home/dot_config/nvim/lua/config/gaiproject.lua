-- Configuration for gai ProjectSpec files (~/.gai/projects/*.gp)

vim.cmd([[
  autocmd BufRead,BufNewFile ~/.gai/projects/*.gp setlocal filetype=gaiproject
  autocmd BufRead,BufNewFile ~/.gai/projects/*.gp setlocal
        \ comments=fb:*,://,b:#
        \ commentstring=#%s
        \ nowrap
        \ textwidth=100
]])
