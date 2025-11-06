-- Configuration for gai ProjectSpec files (~/.gai/projects/*.md)

vim.cmd([[
  autocmd BufRead,BufNewFile ~/.gai/projects/*.md setlocal filetype=gaiproject
  autocmd BufRead,BufNewFile ~/.gai/projects/*.md setlocal
        \ comments=fb:*,://,b:#
        \ commentstring=#%s
        \ nowrap
        \ textwidth=100
]])
