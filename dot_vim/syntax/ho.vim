" Syntax highlighting for homeorg (.ho) files.

runtime! syntax/txt.vim

syn cluster homeOrgTagRegions add=HomeOrgContext,HomeOrgLink,HomeOrgPragma,HomeOrgProject,HomeOrgProjectBox,HomeOrgRole,HomeOrgWhoContext,HomeOrgDate

" Links (ex: [[foobar.ho]])
syn region HomeOrgLink start="\[\[" end="\]\]" oneline
highlight HomeOrgLink ctermfg=green

" Contexts (ex: @foobar of john@)
syn region HomeOrgContext start="\s\zs@[A-Za-z]" end="\ze\(\s\|$\)" oneline
highlight HomeOrgContext ctermfg=red
syn region HomeOrgWhoContext start="\s\zs[A-Za-z]\+\ze@$" end="$" oneline
syn region HomeOrgWhoContext start="\s\zs[A-Za-z]\+\ze@\s" end="\ze\s" oneline
highlight HomeOrgWhoContext ctermfg=magenta

syn region HomeOrgRole start="\s\zs#[A-Za-z]" end="\ze]\?\(\s\|$\)" oneline
highlight HomeOrgRole ctermfg=darkgreen

syn region HomeOrgProject start="\s\zs+[0-9]*[A-Za-z]" end="\ze\(\s\|$\)" oneline
highlight HomeOrgProject ctermfg=yellow
syn region HomeOrgProjectBox start="\s\zs\[[0-9]*[A-Za-z]" end="]\ze\(\s\|$\)" oneline
highlight HomeOrgProjectBox ctermfg=darkyellow

syn region HomeOrgPragma start="^\s*::\s\?" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgPragma ctermfg=grey

syn region HomeOrgTodo start="^\s*o" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgTodo cterm=bold

syn region HomeOrgNote start="^\s*\-\s" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgNote cterm=italic
