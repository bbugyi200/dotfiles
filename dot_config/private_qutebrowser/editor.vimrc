set backspace=2

" yank to clipboard
if has("clipboard")
  set clipboard=unnamed " copy to the system clipboard

  if has("unnamedplus") " X11 support
    set clipboard+=unnamedplus
  endif
endif

nnoremap <CR> :wq<CR> | imap <CR> <Esc><CR>
nnoremap Y y$
nnoremap ,q :s/\(-t \\|\/\)//g<CR><CR>
nnoremap ,/ :s/\(:open \(-t \)\?\)/\1\//<CR>A
nnoremap ] /\v:open (-t )?\zs.<CR>
nmap [ ]hi 
nnoremap <C-]> 04W<C-a>

" #################### VIM PLUGIN CONFIGURATIONS ####################
call plug#begin('~/.vim/bundle')

Plug 'tpope/vim-surround'

call plug#end()
