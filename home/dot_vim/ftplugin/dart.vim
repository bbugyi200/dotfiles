nmap <LocalLeader>o :CocOutline<CR>
let b:run_cmd = ':Silent tidy_dart ' . expand('%:p') . ' && dart format ' . expand('%:p')
