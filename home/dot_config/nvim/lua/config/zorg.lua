-- Configuration for *.zo (zorg) files lives here.

vim.cmd([[
  " Custom Completion (<c-x><c-u>)
  function! ZorgCompleteFunc(findstart, base)
    if a:findstart > 0
      return col('.')
    endif
    let dict = readfile(expand('~/org/.index'))
    return dict
  endfunction

  autocmd BufRead,BufNewFile *.zo setlocal filetype=zorg
  autocmd BufRead,BufNewFile *.zoq setlocal filetype=zorg.zorq
  autocmd BufRead,BufNewFile *.zot setlocal filetype=zorg.jinja
  autocmd BufRead,BufNewFile *.zo,*.zot,*.zoq setlocal
        \ comments=fb:*,://,b:#
        \ commentstring=#%s
        \ completefunc=ZorgCompleteFunc
        \ formatlistpat=^\\s*[*-ox~<>]\\s\\+
        \ formatoptions=ojnqr
        \ nowrap
        \ textwidth=100
]])

-- KEYMAP: <leader>zii
-- KEYMAP: <leader>zin
vim.cmd([[
  nnoremap <nowait> <leader>zii :wa<cr>:e ~/org/inbox.zo<cr>GO-<space>
  nnoremap <nowait> <leader>zin :e ~/org/inbox.zo<cr>
]])
