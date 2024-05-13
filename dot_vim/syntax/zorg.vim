" Syntax highlighting for zorg (.zo) files.

syn cluster zorgPriority add=ZorgP0,ZorgP1,ZorgP2,ZorgP3,ZorgP4,ZorgP5
syn cluster zorg add=ZorgContext,ZorgPageLink,ZorgBlockLink,ZorgProject,ZorgProjectBox,ZorgRole,ZorgPerson,ZorgDate,ZorgUrl,ZorgChildTodoBullet,ZID,ZorgP0,ZorgP1,ZorgP2,ZorgP3,ZorgP4,ZorgP5,ZorgProperty
syn cluster h1Zorg add=ZorgH1Context,ZorgH1Project,ZorgH1Property,ZorgH1Role,ZorgH1Person,ZorgH1PageLink,ZorgH1Date
syn cluster h2Zorg add=ZorgH2Context,ZorgH2Project,ZorgH2Property,ZorgH2Role,ZorgH2Person,ZorgH2PageLink,ZorgH2Date
syn cluster h3Zorg add=ZorgH3Project,ZorgH3PageLink,ZorgH3Context,ZorgH3Property
syn cluster h4Zorg add=ZorgH4Project,ZorgH4PageLink,ZorgH4Context,ZorgH4Property

" Sections / Headers
syn region H1 start="^######### " end="$" contains=@h1Zorg oneline
syn region H2 start="^======= " end="$" contains=@h2Zorg oneline
syn region H3 start="^\*\*\*\*\* " end="$" contains=@h3Zorg oneline
syn region H4 start="^--- " end="$" contains=@h4Zorg oneline
highlight H1 ctermfg=213 cterm=italic,standout
highlight H2 ctermfg=108 cterm=italic,standout
highlight H3 ctermfg=183 cterm=italic,standout
highlight H4 ctermfg=216 cterm=italic,standout

" Web URLs (ex: http://www.example.com)
syn match ZorgUrl "http[s]\?:\/\/\(\S\+\)[^) ,.!?;:]" contains=@NoSpell,EndP
highlight ZorgUrl ctermfg=blue cterm=underline

" Local Page Links (ex: [[foobar]])
syn region ZorgH1PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgH2PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgH3PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgH4PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgPageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
highlight ZorgH1PageLink cterm=bold ctermbg=213 ctermfg=white
highlight ZorgH2PageLink cterm=bold ctermbg=108 ctermfg=white
highlight ZorgH3PageLink cterm=bold ctermbg=183 ctermfg=white
highlight ZorgH4PageLink cterm=bold ctermbg=216 ctermfg=white
highlight ZorgPageLink ctermfg=green

" Local Block Links (ex: ((baz)))
syn region ZorgBlockLink start="\(^\|\s\|(\)\zs((" end="))" contains=@NoSpell oneline
highlight ZorgBlockLink ctermfg=122

" Priorities (ex: P0)
syn region ZorgP0 start="\s\zsP0" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP0 cterm=bold ctermfg=white ctermbg=darkred
syn region ZorgP1 start="\s\zsP1" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP1 cterm=bold ctermfg=white ctermbg=208
syn region ZorgP2 start="\s\zsP2" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP2 cterm=bold ctermfg=black ctermbg=darkyellow
syn region ZorgP3 start="\s\zsP3" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP3 cterm=bold ctermfg=black ctermbg=darkgreen
syn region ZorgP4 start="\s\zsP4" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP4 cterm=bold ctermfg=black ctermbg=252
syn region ZorgP5 start="\s\zsP[56789]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP5 cterm=bold ctermfg=black ctermbg=grey

" Properties
syn region ZorgH1Property start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgH2Property start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgH3Property start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgH4Property start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgProperty start="\(\s\|(\)\zs[a-z_]\+::[a-z_]*" end="\ze[ \n]" contains=@NoSpell,@zorg oneline
highlight ZorgH1Property cterm=underline ctermbg=213 ctermfg=232
highlight ZorgH2Property cterm=underline ctermbg=108 ctermfg=232
highlight ZorgH3Property cterm=underline ctermbg=183 ctermfg=232
highlight ZorgH4Property cterm=underline ctermbg=216 ctermfg=232
highlight ZorgProperty cterm=bold ctermfg=218

" Contexts (ex: @home)
syn region ZorgH1Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH2Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH3Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH4Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgContext start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
highlight ZorgH1Context cterm=bold,italic ctermbg=213 ctermfg=124
highlight ZorgH2Context cterm=bold,italic ctermbg=108 ctermfg=124
highlight ZorgH3Context cterm=bold,italic ctermbg=183 ctermfg=124
highlight ZorgH4Context cterm=bold,italic ctermbg=216 ctermfg=124
highlight ZorgContext cterm=bold ctermfg=red

" People (ex: %john)
syn region ZorgH1Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region ZorgH2Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region ZorgPerson start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
highlight ZorgH1Person ctermbg=213 cterm=bold ctermfg=94
highlight ZorgH2Person ctermbg=108 cterm=bold ctermfg=94
highlight ZorgPerson ctermfg=darkcyan

" Roles / Areas of Responsibility (ex: #work)
syn region ZorgH1Role start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH2Role start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgRole start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgH1Role cterm=bold,italic ctermbg=213 ctermfg=white
highlight ZorgH2Role cterm=bold,italic ctermbg=108 ctermfg=white
highlight ZorgRole ctermfg=darkgreen

" Projects (ex: +foobar)
syn region ZorgH1Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH2Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH3Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH4Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgProject start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgH1Project cterm=bold ctermbg=213 ctermfg=232
highlight ZorgH2Project cterm=bold ctermbg=108 ctermfg=232
highlight ZorgH3Project cterm=bold ctermbg=183 ctermfg=232
highlight ZorgH4Project cterm=bold ctermbg=216 ctermfg=232
highlight ZorgProject ctermfg=yellow

" Dates (ex: 2024-01-12, 240112)
syn match ZorgH1Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\)\ze[ \n,.?!;:)]"
syn match ZorgH2Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\)\ze[ \n,.?!;:)]"
syn match ZorgDate "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\)\ze[ \n,.?!;:)]"
highlight ZorgH1Date ctermbg=213 ctermfg=white cterm=underline
highlight ZorgH2Date ctermbg=108 ctermfg=white cterm=underline
highlight ZorgDate cterm=underline

" IDs (ex: 240112#00)
syn match ZID "[0-9][0-9][01][0-9][0123][0-9]#[A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9]\?\ze[ \n,.?!;:)]"
highlight ZID cterm=underline

" # | Comments
syn region ZorgComment start="^\s*# " end="$" contains=@zorg oneline
syn region ZorgComment start="^#$" end="$" contains=@zorg oneline
highlight ZorgComment ctermfg=grey

" o | Todos
syn match ZorgTodo "^\s*o\s.*\(\n\s\s\+[^o\-*<>].*\)*" contains=@zorg
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
