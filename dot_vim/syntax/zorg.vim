" Syntax highlighting for zorg (.zo) files.

syn cluster zorgPriority add=ZorgP0,ZorgP1,ZorgP2,ZorgP3,ZorgP4,ZorgP5,ZorgP6,ZorgP7,ZorgP8,ZorgP9
syn cluster zorg add=ZorgContext,ZorgPageLink,ZorgBlockLink,ZorgProject,ZorgProjectBox,ZorgArea,ZorgPerson,ZorgDate,ZorgUrl,ZorgChildTodoBullet,ZID,ZIDLink,IDLink,LocalLink,ZorgP0,ZorgP1,ZorgP2,ZorgP3,ZorgP4,ZorgP5,ZorgP6,ZorgP7,ZorgP8,ZorgP9,ZorgProperty
syn cluster h1Zorg add=ZorgH1Context,ZorgH1Project,ZorgH1Property,ZorgH1Area,ZorgH1Person,ZorgH1PageLink,ZorgH1Date
syn cluster h2Zorg add=ZorgH2Context,ZorgH2Project,ZorgH2Property,ZorgH2Area,ZorgH2Person,ZorgH2PageLink,ZorgH2Date
syn cluster h3Zorg add=ZorgH3Project,ZorgH3PageLink,ZorgH3Context,ZorgH3Property,ZorgH3Person,ZorgH3Area,ZorgH3Date
syn cluster h4Zorg add=ZorgH4Project,ZorgH4PageLink,ZorgH4Context,ZorgH4Property,ZorgH4Person,ZorgH4Area,ZorgH4Date

" Sections / Headers
syn region H1 start="^################################ " end="$" contains=@h1Zorg oneline
syn region H2 start="^======================== " end="$" contains=@h2Zorg oneline
syn region H3 start="^++++++++++++++++ " end="$" contains=@h3Zorg oneline
syn region H4 start="^-------- " end="$" contains=@h4Zorg oneline
highlight H1 ctermfg=222 cterm=italic,standout
highlight H2 ctermfg=109 cterm=italic,standout
highlight H3 ctermfg=182 cterm=italic,standout
highlight H4 ctermfg=250 cterm=italic,standout

" Web URLs (ex: http://www.example.com)
syn match ZorgUrl "http[s]\?:\/\/\(\S\+\)[^) ,.!?;:]" contains=@NoSpell,EndP
highlight ZorgUrl ctermfg=blue cterm=underline

" Local Page Links (ex: [[foobar]])
syn region ZorgH1PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgH2PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgH3PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgH4PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region ZorgPageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
highlight ZorgH1PageLink cterm=bold ctermbg=222 ctermfg=232
highlight ZorgH2PageLink cterm=bold ctermbg=109 ctermfg=232
highlight ZorgH3PageLink cterm=bold ctermbg=182 ctermfg=232
highlight ZorgH4PageLink cterm=bold ctermbg=250 ctermfg=232
highlight ZorgPageLink ctermfg=green

" Local Block Links (ex: ((baz)))
syn region ZorgBlockLink start="\(^\|\s\|(\)\zs((" end="))" contains=@NoSpell oneline
highlight ZorgBlockLink ctermfg=122

" Priorities (ex: P0)
syn region ZorgP0 start="\(\s\zs\|################################\s\)P0" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP0 cterm=bold ctermfg=white ctermbg=darkred
syn region ZorgP1 start="\(\s\zs\|################################\s\)P1" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP1 cterm=bold ctermfg=white ctermbg=208
syn region ZorgP2 start="\(\s\zs\|################################\s\)P2" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP2 cterm=bold ctermfg=black ctermbg=darkyellow
syn region ZorgP3 start="\(\s\zs\|################################\s\)P3" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP3 cterm=bold ctermfg=black ctermbg=darkgreen
syn region ZorgP4 start="\(\s\zs\|################################\s\)P4" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP4 cterm=bold ctermfg=black ctermbg=252
syn region ZorgP5 start="\(\s\zs\|################################\s\)P5" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP5 cterm=bold ctermfg=black ctermbg=250
syn region ZorgP6 start="\(\s\zs\|################################\s\)P6" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP6 cterm=bold ctermfg=black ctermbg=248
syn region ZorgP7 start="\(\s\zs\|################################\s\)P7" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP7 cterm=bold ctermfg=254 ctermbg=246
syn region ZorgP8 start="\(\s\zs\|################################\s\)P8" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP8 cterm=bold ctermfg=252 ctermbg=244
syn region ZorgP9 start="\(\s\zs\|################################\s\)P9" end="\ze[ \n),.?!;:]" oneline
highlight ZorgP9 cterm=bold ctermfg=252 ctermbg=241

" Properties
syn region ZorgH1Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgH2Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgH3Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgH4Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n]" contains=@NoSpell oneline
syn region ZorgProperty start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ )\n]" contains=@NoSpell,@zorg oneline
highlight ZorgH1Property cterm=underline ctermbg=222 ctermfg=54
highlight ZorgH2Property cterm=underline ctermbg=109 ctermfg=54
highlight ZorgH3Property cterm=underline ctermbg=182 ctermfg=54
highlight ZorgH4Property cterm=underline ctermbg=250 ctermfg=54
highlight ZorgProperty cterm=bold ctermfg=218

" Contexts (ex: @home)
syn region ZorgH1Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH2Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH3Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgH4Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region ZorgContext start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
highlight ZorgH1Context cterm=bold ctermbg=222 ctermfg=160
highlight ZorgH2Context cterm=bold ctermbg=109 ctermfg=160
highlight ZorgH3Context cterm=bold ctermbg=182 ctermfg=160
highlight ZorgH4Context cterm=bold ctermbg=250 ctermfg=160
highlight ZorgContext cterm=bold ctermfg=red

" People (ex: %john)
syn region ZorgH1Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region ZorgH2Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region ZorgH3Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region ZorgH4Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region ZorgPerson start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
highlight ZorgH1Person ctermbg=222 cterm=bold ctermfg=52
highlight ZorgH2Person ctermbg=109 cterm=bold ctermfg=52
highlight ZorgH3Person ctermbg=182 cterm=bold ctermfg=52
highlight ZorgH4Person ctermbg=250 cterm=bold ctermfg=52
highlight ZorgPerson ctermfg=darkcyan

" Areas of Responsibility (ex: #work)
syn region ZorgH1Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH2Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH3Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH4Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgArea start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgH1Area cterm=bold,italic ctermbg=222 ctermfg=22
highlight ZorgH2Area cterm=bold,italic ctermbg=109 ctermfg=22
highlight ZorgH3Area cterm=bold,italic ctermbg=182 ctermfg=22
highlight ZorgH4Area cterm=bold,italic ctermbg=250 ctermfg=22
highlight ZorgArea ctermfg=darkgreen

" Projects (ex: +foobar)
syn region ZorgH1Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH2Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH3Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgH4Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region ZorgProject start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight ZorgH1Project cterm=bold,underline ctermbg=222 ctermfg=232
highlight ZorgH2Project cterm=bold,underline ctermbg=109 ctermfg=232
highlight ZorgH3Project cterm=bold,underline ctermbg=182 ctermfg=232
highlight ZorgH4Project cterm=bold,underline ctermbg=250 ctermfg=232
highlight ZorgProject ctermfg=208

" Dates (ex: 2024-01-12, 240112)
syn match ZorgH1Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match ZorgH2Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match ZorgH3Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match ZorgH4Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match ZorgDate "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
highlight ZorgH1Date ctermbg=222 ctermfg=232 cterm=underline
highlight ZorgH2Date ctermbg=109 ctermfg=232 cterm=underline
highlight ZorgH3Date ctermbg=182 ctermfg=232 cterm=underline
highlight ZorgH4Date ctermbg=250 ctermfg=232 cterm=underline
highlight ZorgDate cterm=underline

" ZIDs (ex: 240112#00)
syn match ZID "[0-9][0-9][01][0-9][0123][0-9]#[A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9]\?\ze[ \n,.?!;:)]"
highlight ZID cterm=underline

" ZID Links
syn match ZIDLink "\[[0-9][0-9][01][0-9][0123][0-9]#[A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9]\?\]\ze[ \n,.?!;:)]"
highlight ZIDLink ctermfg=122

" ID Links
syn match IDLink "\[#[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
highlight IDLink ctermfg=87

" Local Links
syn match LocalLink "\[[0-9]\+\]\ze[ \n,.?!;:)]"
highlight LocalLink ctermfg=193

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
syn region ZorgChildTodoBullet start="^\s*\zs\*\ze\(\s\|$\)" end="\ze\(\s\|$\)" contains=@zorg oneline
highlight ZorgChildTodoBullet cterm=bold

" - | Notes
syn match ZorgNote "^\s*\-\s.*\(\n\s\s\+[^o*<>].*\)*" contains=@zorg
highlight ZorgNote cterm=italic
