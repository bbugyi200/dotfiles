" Syntax highlighting for homeorg (.ho) files.

syn cluster homeOrgTagRegions add=HomeOrgContext,HomeOrgLink,HomeOrgPragma,HomeOrgProject,HomeOrgProjectBox,HomeOrgRole,HomeOrgWhoContext,HomeOrgDate

" Links (ex: [[foobar.ho]])
syn region HomeOrgLink start="\[\[" end="\]\]" oneline
highlight HomeOrgLink ctermfg=green

" Contexts (ex: @home or john@)
syn region HomeOrgContext start="\(\s\|(\)\zs@[A-Za-z]" end="\ze\(\s\|$\)" oneline
highlight HomeOrgContext ctermfg=red
syn region HomeOrgWhoContext start="\(\s\|(\)\zs[A-Za-z]\+\ze@$" end="$" oneline
syn region HomeOrgWhoContext start="\(\s\|(\)\zs[A-Za-z]\+\ze@\s" end="\ze\s" oneline
highlight HomeOrgWhoContext ctermfg=magenta

" Roles (ex: #work)
syn region HomeOrgRole start="\(\s\|(\)\zs#[A-Za-z]" end="\ze]\?\(\s\|$\)" oneline
highlight HomeOrgRole ctermfg=darkgreen

" Projects (ex: [foobar] or +foobar)
syn region HomeOrgProject start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze\(\s\|$\)" oneline
highlight HomeOrgProject ctermfg=yellow
syn region HomeOrgProjectBox start="\s\zs\[[0-9]*[A-Za-z]" end="]\ze\(\s\|$\)" oneline
highlight HomeOrgProjectBox ctermfg=darkyellow

" :: Comments
syn region HomeOrgPragma start="^\s*::\s\?" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgPragma ctermfg=grey

" o Todos
syn region HomeOrgTodo start="^\s*o\s" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgTodo cterm=bold

" - Notes
syn region HomeOrgNote start="^\s*\-\s" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgNote cterm=italic
