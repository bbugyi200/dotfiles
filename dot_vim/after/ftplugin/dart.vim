setlocal textwidth=0

function! ToggleLibTest()
  let l:current_file = expand("%:p")
  let l:lib_pattern = 'lib/\(.*\).dart$'
  let l:test_pattern = 'test/\(.*\)_test.dart$'
  let l:lib_file = substitute(l:current_file, l:test_pattern, 'lib/\1.dart', '')
  let l:test_file = substitute(l:current_file, l:lib_pattern, 'test/\1_test.dart', '')

  if l:current_file != l:lib_file
    execute 'edit' l:lib_file
  elseif l:current_file != l:test_file
    execute 'edit' l:test_file
  endif
endfunction

" Check if the current file matches the desired patterns before creating the mapping
if expand("%:p") =~ 'lib/\(.*\).dart$' || expand("%:p") =~ 'test/\(.*\)_test.dart$'
  nnoremap <silent> <buffer> <LocalLeader>t :call ToggleLibTest()<CR>
endif
