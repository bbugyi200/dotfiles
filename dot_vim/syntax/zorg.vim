" Syntax highlighting for zorg (.zo) files.

syn cluster zorgPriority add=P0,P1,P2,P3,P4,P5,P6,P7,P8,P9
syn cluster zorg add=Context,PageLink,EmbeddedLink,Project,ProjectBox,Area,Person,Date,Url,ChildTodoBullet,ZID,ZIDLink,IDLink,LocalLink,RefLink,P0,P1,P2,P3,P4,P5,P6,P7,P8,P9,Property
syn cluster h1 add=H1Context,H1Project,H1Property,H1Area,H1Person,H1PageLink,H1Date
syn cluster h2 add=H2Context,H2Project,H2Property,H2Area,H2Person,H2PageLink,H2Date
syn cluster h3 add=H3Project,H3PageLink,H3Context,H3Property,H3Person,H3Area,H3Date
syn cluster h4 add=H4Project,H4PageLink,H4Context,H4Property,H4Person,H4Area,H4Date

" Sections / Headers
syn region H1 start="^################################ " end="$" contains=@h1 oneline
syn region H2 start="^======================== " end="$" contains=@h2 oneline
syn region H3 start="^++++++++++++++++ " end="$" contains=@h3 oneline
syn region H4 start="^-------- " end="$" contains=@h4 oneline
highlight H1 ctermfg=222 cterm=italic,standout
highlight H2 ctermfg=109 cterm=italic,standout
highlight H3 ctermfg=182 cterm=italic,standout
highlight H4 ctermfg=250 cterm=italic,standout

" Web URLs (ex: http://www.example.com)
syn match Url "http[s]\?:\/\/\(\S\+\)[^) ,.!?;:\]]" contains=@NoSpell,EndP
highlight Url ctermfg=blue cterm=underline

" Priorities (ex: P0)
syn region P0 start="\(\s\zs\|################################\s\)P0" end="\ze[ \n),.?!;:]" oneline
highlight P0 cterm=bold ctermfg=white ctermbg=darkred
syn region P1 start="\(\s\zs\|################################\s\)P1" end="\ze[ \n),.?!;:]" oneline
highlight P1 cterm=bold ctermfg=white ctermbg=208
syn region P2 start="\(\s\zs\|################################\s\)P2" end="\ze[ \n),.?!;:]" oneline
highlight P2 cterm=bold ctermfg=black ctermbg=darkyellow
syn region P3 start="\(\s\zs\|################################\s\)P3" end="\ze[ \n),.?!;:]" oneline
highlight P3 cterm=bold ctermfg=black ctermbg=darkgreen
syn region P4 start="\(\s\zs\|################################\s\)P4" end="\ze[ \n),.?!;:]" oneline
highlight P4 cterm=bold ctermfg=black ctermbg=252
syn region P5 start="\(\s\zs\|################################\s\)P5" end="\ze[ \n),.?!;:]" oneline
highlight P5 cterm=bold ctermfg=black ctermbg=250
syn region P6 start="\(\s\zs\|################################\s\)P6" end="\ze[ \n),.?!;:]" oneline
highlight P6 cterm=bold ctermfg=black ctermbg=248
syn region P7 start="\(\s\zs\|################################\s\)P7" end="\ze[ \n),.?!;:]" oneline
highlight P7 cterm=bold ctermfg=254 ctermbg=246
syn region P8 start="\(\s\zs\|################################\s\)P8" end="\ze[ \n),.?!;:]" oneline
highlight P8 cterm=bold ctermfg=252 ctermbg=244
syn region P9 start="\(\s\zs\|################################\s\)P9" end="\ze[ \n),.?!;:]" oneline
highlight P9 cterm=bold ctermfg=252 ctermbg=241

" Properties
syn region H1Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell oneline
syn region H2Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell oneline
syn region H3Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell oneline
syn region H4Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell oneline
syn region Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
highlight H1Property cterm=underline ctermbg=222 ctermfg=54
highlight H2Property cterm=underline ctermbg=109 ctermfg=54
highlight H3Property cterm=underline ctermbg=182 ctermfg=54
highlight H4Property cterm=underline ctermbg=250 ctermfg=54
highlight Property cterm=bold ctermfg=218

" Contexts (ex: @home)
syn region H1Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region H2Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region H3Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region H4Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
highlight H1Context cterm=bold ctermbg=222 ctermfg=160
highlight H2Context cterm=bold ctermbg=109 ctermfg=160
highlight H3Context cterm=bold ctermbg=182 ctermfg=160
highlight H4Context cterm=bold ctermbg=250 ctermfg=160
highlight Context cterm=bold ctermfg=red

" People (ex: %john)
syn region H1Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region H2Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region H3Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region H4Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
highlight H1Person ctermbg=222 cterm=bold ctermfg=52
highlight H2Person ctermbg=109 cterm=bold ctermfg=52
highlight H3Person ctermbg=182 cterm=bold ctermfg=52
highlight H4Person ctermbg=250 cterm=bold ctermfg=52
highlight Person ctermfg=darkcyan

" Areas of Responsibility (ex: #work)
syn region H1Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H2Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H3Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H4Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight H1Area cterm=bold,italic ctermbg=222 ctermfg=22
highlight H2Area cterm=bold,italic ctermbg=109 ctermfg=22
highlight H3Area cterm=bold,italic ctermbg=182 ctermfg=22
highlight H4Area cterm=bold,italic ctermbg=250 ctermfg=22
highlight Area ctermfg=darkgreen

" Projects (ex: +foobar)
syn region H1Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H2Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H3Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H4Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
highlight H1Project cterm=bold,underline ctermbg=222 ctermfg=232
highlight H2Project cterm=bold,underline ctermbg=109 ctermfg=232
highlight H3Project cterm=bold,underline ctermbg=182 ctermfg=232
highlight H4Project cterm=bold,underline ctermbg=250 ctermfg=232
highlight Project ctermfg=208

" Dates (ex: 2024-01-12, 240112)
syn match H1Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match H2Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match H3Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match H4Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
highlight H1Date ctermbg=222 ctermfg=232 cterm=underline
highlight H2Date ctermbg=109 ctermfg=232 cterm=underline
highlight H3Date ctermbg=182 ctermfg=232 cterm=underline
highlight H4Date ctermbg=250 ctermfg=232 cterm=underline
highlight Date cterm=underline

" ZIDs (ex: 240112#00)
syn match ZID "[0-9][0-9][01][0-9][0123][0-9]#[A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9]\?\ze[ \n,.?!;:)]"
highlight ZID cterm=underline

" Local Page Links (ex: [[foobar]])
syn region H1PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region H2PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region H3PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region H4PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
highlight H1PageLink cterm=bold ctermbg=222 ctermfg=232
highlight H2PageLink cterm=bold ctermbg=109 ctermfg=232
highlight H3PageLink cterm=bold ctermbg=182 ctermfg=232
highlight H4PageLink cterm=bold ctermbg=250 ctermfg=232
highlight PageLink ctermfg=green

" Embedded Links [ex: ((baz))]
syn region EmbeddedLink start="\(^\|\s\|(\)\zs((" end="))" contains=@NoSpell oneline
highlight EmbeddedLink ctermfg=122

" ZID Links
syn match ZIDLink "\[[0-9][0-9][01][0-9][0123][0-9]#[A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9]\?\]\ze[ \n,.?!;:)]"
highlight ZIDLink ctermfg=122

" ID Links
syn match IDLink "\[#[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
highlight IDLink ctermfg=87

" Local Links
syn match LocalLink "\[[0-9]\+\]\ze[ \n,.?!;:)]"
highlight LocalLink ctermfg=193

" Ref Links
syn match RefLink "\[@[B-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
highlight RefLink ctermfg=11

" # | Comments
syn region Comment start="^\s*# " end="$" contains=@zorg oneline
syn region Comment start="^#$" end="$" contains=@zorg oneline
highlight Comment ctermfg=grey

" o | Todos
syn match OpenTodo "^\s*o\s.*\(\n\s\s\+[^o\-*<>].*\)*" contains=@zorg
highlight OpenTodo cterm=bold

" ~ | Canceled Todos
syn region CanceledTodo start="^\s*\~\s" end="$" contains=@zorg oneline
highlight CanceledTodo cterm=italic ctermfg=252

" > | Todo Group (used to group a set of todos under a single parent todo)
syn region TodoGroup start="^\s*\zs>\s" end="$" contains=@zorg oneline
highlight TodoGroup cterm=underline

" < | Blocked Todo
syn region BlockedTodo start="^\s*\zs<\s" end="$" contains=@zorgPriority oneline
highlight BlockedTodo cterm=standout

" * | Child Todo Bullet / Waiting For Bullet
syn region ChildTodoBullet start="^\s*\zs\*\ze\(\s\|$\)" end="\ze\(\s\|$\)" contains=@zorg oneline
highlight ChildTodoBullet cterm=bold

" - | Notes
syn match Note "^\s*\-\s.*\(\n\s\s\+[^o*<>].*\)*" contains=@zorg
highlight Note cterm=italic
