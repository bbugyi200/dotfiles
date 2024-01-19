" Syntax highlighting for zorg (.z) files.

syn cluster homeOrgTagRegions add=HomeOrgContext,HomeOrgLink,HomeOrgProject,HomeOrgProjectBox,HomeOrgRole,HomeOrgWhoContext,HomeOrgDate,HomeOrgUrl,HomeOrgChildTodoBullet,HomeOrgDate,HomeOrgHighPriority,HomeOrgMediumPriority,HomeOrgLowPriority

" Sections / Headers
syn region WildMenu start="###" end="###$" oneline
syn region Type start="^\s*===" end="===$" oneline
syn region Function start="^\s*---" end="---$" oneline

" Web URLs (ex: http://www.example.com)
syn match HomeOrgUrl "http[s]\?:\/\/\(\S\+\)[^) ,.!?;:]" contains=@NoSpell,EndP
highlight HomeOrgUrl ctermfg=blue cterm=underline

" Local Links (ex: [[foobar.ho]])
syn region HomeOrgLink start="\(^\|\s\|(\)\zs\[\[" end="\]\]" oneline
highlight HomeOrgLink ctermfg=green

" Contexts (ex: @home or john@)
syn region HomeOrgContext start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@homeOrgTagRegions oneline
highlight HomeOrgContext cterm=bold ctermfg=red
syn region HomeOrgWhoContext start="\(\s\|(\)\zs[A-Za-z]\+\ze@" end="@\ze[) \n,.?!;:']" oneline
highlight HomeOrgWhoContext ctermfg=darkcyan

" Priority Contexts (ex: @A/2024-01-19)
syn region HomeOrgHighPriority start="\(\s\|(\)\zs@A" end="\ze[ \n),.?!;:]" oneline
highlight HomeOrgHighPriority cterm=bold ctermfg=white ctermbg=darkred
syn region HomeOrgMediumPriority start="\(\s\|(\)\zs@B" end="\ze[ \n),.?!;:]" oneline
highlight HomeOrgMediumPriority cterm=bold ctermfg=black ctermbg=darkyellow
syn region HomeOrgLowPriority start="\(\s\|(\)\zs@C" end="\ze[ \n),.?!;:]" oneline
highlight HomeOrgLowPriority cterm=bold ctermfg=black ctermbg=darkgreen

" Roles (ex: #work)
syn region HomeOrgRole start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight HomeOrgRole ctermfg=darkgreen

" Projects (ex: [foobar] or +foobar)
syn region HomeOrgProject start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight HomeOrgProject ctermfg=yellow
syn region HomeOrgProjectBox start="\(\s\|(\)\zs\[[0-9]*[A-Za-z]" end="]\ze[ \n),.?!;:]" oneline
highlight HomeOrgProjectBox ctermfg=darkyellow

" Dates (ex: 2024-01-12)
syn match HomeOrgDate "2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\ze[ \n,.?!;:]"
highlight HomeOrgDate cterm=underline

" # | Comments
syn region HomeOrgComment start="^\s*# " end="$" contains=@homeOrgTagRegions oneline
syn region HomeOrgComment start="^#$" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgComment ctermfg=grey

" o | Todos
syn region HomeOrgTodo start="^\s*o\s" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgTodo cterm=bold

" > | Todo Group (used to group a set of todos under a single parent todo)
syn region HomeOrgTodoGroup start="^\s*\zs>\s" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgTodoGroup cterm=underline

" < | Blocked Todo
syn region HomeOrgBlockedTodo start="^\s*\zs<\s" end="$" contains=@homeOrgTagRegions oneline
highlight HomeOrgBlockedTodo cterm=standout

" * | Child Todo Bullet / Waiting For Bullet
syn region HomeOrgChildTodoBullet start="^\s*\*" end="\ze." contains=@homeOrgTagRegions oneline
highlight HomeOrgChildTodoBullet cterm=reverse

" - | Notes
syn match HomeOrgNote "^\s*\-\s.*\(\n\s\s\+[^o*<>].*\)*" contains=@homeOrgTagRegions
highlight HomeOrgNote cterm=italic
