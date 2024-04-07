" Syntax highlighting for zorg (.zo) files.

syn cluster zorgPriority add=ZorgA,ZorgB,ZorgC,ZorgD
syn cluster zorg add=ZorgContext,ZorgPageLink,ZorgBlockLink,ZorgProject,ZorgProjectBox,ZorgRole,ZorgPerson,ZorgDate,ZorgUrl,ZorgChildTodoBullet,ZorgDate,ZorgA,ZorgB,ZorgC,ZorgD,ZorgProperty
syn cluster h1Zorg add=ZorgH1Context,ZorgH1Project,ZorgH1Property
syn cluster h2Zorg add=ZorgH2Context,ZorgH2Project,ZorgH2Property

" Sections / Headers
syn region H1 start="^######### " end="$" contains=@h1Zorg oneline
syn region H2 start="^======= " end="$" contains=@h2Zorg oneline
syn region H3 start="^\*\*\*\*\* " end="$" oneline
syn region H4 start="^--- " end="$" oneline
highlight H1 ctermfg=218 cterm=italic,standout
highlight H2 ctermfg=108 cterm=italic,standout
highlight H3 ctermfg=183 cterm=italic,standout
highlight H4 ctermfg=216 cterm=italic,standout

" Web URLs (ex: http://www.example.com)
syn match ZorgUrl "http[s]\?:\/\/\(\S\+\)[^) ,.!?;:]" contains=@NoSpell,EndP
highlight ZorgUrl ctermfg=blue cterm=underline

" Local Page Links (ex: [[foobar]])
syn region ZorgPageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
highlight ZorgPageLink ctermfg=green

" Local Block Links (ex: ((baz)))
syn region ZorgBlockLink start="\(^\|\s\|(\)\zs((" end="))" contains=@NoSpell oneline
highlight ZorgBlockLink ctermfg=122

" Priorities (ex: [#A])
syn region ZorgA start="\s\zs\[#A\]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgA cterm=bold ctermfg=white ctermbg=darkred
syn region ZorgB start="\s\zs\[#B\]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgB cterm=bold ctermfg=black ctermbg=darkyellow
syn region ZorgC start="\s\zs\[#C\]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgC cterm=bold ctermfg=black ctermbg=darkgreen
syn region ZorgD start="\s\zs\[#D\]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgD cterm=bold ctermfg=white ctermbg=darkgrey

" Properties
syn region ZorgProperty start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell,@zorg oneline
syn region ZorgH1Property start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell,@zorg oneline
syn region ZorgH2Property start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell,@zorg oneline
highlight ZorgProperty cterm=bold ctermfg=219
highlight ZorgH1Property cterm=standout,underline ctermfg=218
highlight ZorgH2Property cterm=standout,underline ctermfg=108

" Contexts (ex: @home)
syn region ZorgContext start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH1Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH2Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
highlight ZorgContext cterm=bold ctermfg=red
highlight ZorgH1Context cterm=standout,bold,italic ctermfg=218 ctermbg=124
highlight ZorgH2Context cterm=standout,bold,italic ctermfg=108 ctermbg=124

" People (ex: %john)
syn region ZorgPerson start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
highlight ZorgPerson ctermfg=darkcyan

" Areas of Responsibility (ex: #work)
syn region ZorgRole start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgRole ctermfg=darkgreen

" Projects (ex: +foobar)
syn region ZorgProject start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH1Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH2Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgProject ctermfg=yellow
highlight ZorgH1Project cterm=standout,bold ctermfg=218
highlight ZorgH2Project cterm=standout,bold ctermfg=108

" Dates (ex: 2024-01-12)
syn match ZorgDate "2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\ze[ \n,.?!;:)]"
highlight ZorgDate cterm=underline

" IDs (ex: 240112#00)
syn match ZorgDate "[0-9][0-9][01][0-9][0123][0-9]#[A-Z0-9][A-Z0-9]\ze[ \n,.?!;:)]"
highlight ZorgDate cterm=underline

" # | Comments
syn region ZorgComment start="^\s*# " end="$" contains=@zorg oneline
syn region ZorgComment start="^#$" end="$" contains=@zorg oneline
highlight ZorgComment ctermfg=grey

" o | Todos
syn match ZorgTodo "^\s*o\s.*\(\n\s\s\+[^o*<>].*\)*" contains=@zorg
highlight ZorgTodo cterm=bold

" ~ | Canceled Todos
syn region ZorgCanceledTodo start="^\s*\~\s" end="$" contains=@zorg oneline
highlight ZorgCanceledTodo cterm=italic ctermfg=252

" > | Todo Group (used to group a set of todos under a single parent todo)
syn region ZorgTodoGroup start="^\s*\zs>\s" end="$" contains=@zorg oneline
highlight ZorgTodoGroup cterm=underline

" < | Blocked Todo
syn region ZorgBlockedTodo start="^\s*\zs<\s" end="$" contains=@zorgPriority oneline
highlight ZorgBlockedTodo cterm=standout

" * | Child Todo Bullet / Waiting For Bullet
syn region ZorgChildTodoBullet start="^\s*\*\ze " end="\ze." contains=@zorg oneline
highlight ZorgChildTodoBullet cterm=reverse

" - | Notes
syn match ZorgNote "^\s*\-\s.*\(\n\s\s\+[^o*<>].*\)*" contains=@zorg
highlight ZorgNote cterm=italic
