" Syntax highlighting for zorg (.zo) files.

syn cluster zorgPriority add=P0,P1,P2,P3,P4,P5,P6,P7,P8,P9
syn cluster zorg add=Context,PageLink,EmbeddedLink,Project,Area,Person,Date,Url,ChildTodoBullet,ZID,ZIDLink,IDLink,LocalLink,RefLink,UrlLink,P0,P1,P2,P3,P4,P5,P6,P7,P8,P9,SpecialProperty,Property,InlineCode,CodeBlock
syn cluster h1 add=H1Context,H1Project,H1Property,H1Area,H1Person,H1PageLink,H1Date,H1RefLink
syn cluster h2 add=H2Context,H2Project,H2Property,H2Area,H2Person,H2PageLink,H2Date,H2RefLink
syn cluster h3 add=H3Project,H3PageLink,H3Context,H3Property,H3Person,H3Area,H3Date,H3RefLink
syn cluster h4 add=H4Project,H4PageLink,H4Context,H4Property,H4Person,H4Area,H4Date,H4RefLink

" Sections / Headers
syn region H1 start="^################################ " end="$" contains=@h1 oneline
syn region H2 start="^======================== " end="$" contains=@h2 oneline
syn region H3 start="^++++++++++++++++ " end="$" contains=@h3 oneline
syn region H4 start="^-------- " end="$" contains=@h4 oneline
highlight H1 guibg=#FFD787 guifg=#333333 gui=italic,standout
highlight H2 guibg=#87AFAF guifg=#333333 gui=italic,standout
highlight H3 guibg=#D7AFD7 guifg=#333333 gui=italic,standout
highlight H4 guibg=#BCBCBC guifg=#333333 gui=italic,standout

" URLs
syn match Url "http[s]\?:\/\/\(\S\+\)[^) ,.!?;:\]]" contains=@NoSpell,EndP
highlight Url guifg=#9999ff gui=underline

" Priorities with GUI colors
syn region P0 start="\(\s\zs\|################################\s\)P0" end="\ze[ \n),.?!;:]" oneline
highlight P0 gui=bold guifg=#FFFFFF guibg=#ff0000
syn region P1 start="\(\s\zs\|################################\s\)P1" end="\ze[ \n),.?!;:]" oneline
highlight P1 gui=bold guifg=#333333 guibg=#FF8700
syn region P2 start="\(\s\zs\|################################\s\)P2" end="\ze[ \n),.?!;:]" oneline
highlight P2 gui=bold guifg=#333333 guibg=#D7AF00
syn region P3 start="\(\s\zs\|################################\s\)P3" end="\ze[ \n),.?!;:]" oneline
highlight P3 gui=bold guifg=#333333 guibg=#00AF00
syn region P4 start="\(\s\zs\|################################\s\)P4" end="\ze[ \n),.?!;:]" oneline
highlight P4 gui=bold guifg=#333333 guibg=#D0D0D0
syn region P5 start="\(\s\zs\|################################\s\)P5" end="\ze[ \n),.?!;:]" oneline
highlight P5 gui=bold guifg=#333333 guibg=#BCBCBC
syn region P6 start="\(\s\zs\|################################\s\)P6" end="\ze[ \n),.?!;:]" oneline
highlight P6 gui=bold guifg=#333333 guibg=#A8A8A8
syn region P7 start="\(\s\zs\|################################\s\)P7" end="\ze[ \n),.?!;:]" oneline
highlight P7 gui=bold guifg=#E4E4E4 guibg=#949494
syn region P8 start="\(\s\zs\|################################\s\)P8" end="\ze[ \n),.?!;:]" oneline
highlight P8 gui=bold guifg=#D0D0D0 guibg=#808080
syn region P9 start="\(\s\zs\|################################\s\)P9" end="\ze[ \n),.?!;:]" oneline
highlight P9 gui=bold guifg=#D0D0D0 guibg=#626262

" Properties
syn region H1Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell,H1Context,H1Project,H1Area,H1Person oneline
syn region H2Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell,H2Context,H2Project,H2Area,H2Person oneline
syn region H3Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell,H3Context,H3Project,H3Area,H3Person oneline
syn region H4Property start="\(\s\|(\)\zs\([A-Za-z_]\+::[a-z_]*\|\[[A-Za-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell,H4Context,H4Project,H4Area,H4Person oneline
syn region Property start="\(\s\|(\)\zs\([a-z_]\+::[a-z_]*\|\[[a-z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell,Context,Project,Area,Person,Url oneline

highlight H1Property gui=underline guibg=#FFD787 guifg=#5F0087
highlight H2Property gui=underline guibg=#87AFAF guifg=#5F0087
highlight H3Property gui=underline guibg=#D7AFD7 guifg=#5F0087
highlight H4Property gui=underline guibg=#BCBCBC guifg=#5F0087
highlight Property gui=bold guifg=#FFAFFF

" Special Properties
syn region SpecialProperty start="\(\s\|(\)\zs\([A-Z_]\+::[a-z_]*\|\[[A-Z_]\+::[^\]]\+\]\)" end="\ze[ \n),.?!;:]" contains=@NoSpell,Context,Project,Area,Person,Url oneline
highlight SpecialProperty gui=underline guifg=#FFAFFF

" Contexts
syn region H1Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region H2Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region H3Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region H4Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline
syn region Context start="\(\s\|(\)\zs@[A-Za-z]" end="\ze[ \n),.?!;:]" contains=@NoSpell,@zorg oneline

highlight H1Context gui=bold guibg=#FFD787 guifg=#D70000
highlight H2Context gui=bold guibg=#87AFAF guifg=#D70000
highlight H3Context gui=bold guibg=#D7AFD7 guifg=#D70000
highlight H4Context gui=bold guibg=#BCBCBC guifg=#D70000
highlight Context gui=bold guifg=#ff5050

" People
syn region H1Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region H2Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region H3Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region H4Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline
syn region Person start="\(\s\|(\)\zs%[0-9]*[A-Za-z]" end="\ze[ '\n),.?!;:]" oneline

highlight H1Person guibg=#FFD787 gui=bold guifg=#5F0000
highlight H2Person guibg=#87AFAF gui=bold guifg=#5F0000
highlight H3Person guibg=#D7AFD7 gui=bold guifg=#5F0000
highlight H4Person guibg=#BCBCBC gui=bold guifg=#5F0000
highlight Person guifg=#ff9966

" Areas
syn region H1Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H2Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H3Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H4Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region Area start="\(\s\|(\)\zs#[A-Za-z]" end="\ze[ \n),.?!;:]" oneline

highlight H1Area gui=bold,italic guibg=#FFD787 guifg=#005F00
highlight H2Area gui=bold,italic guibg=#87AFAF guifg=#005F00
highlight H3Area gui=bold,italic guibg=#D7AFD7 guifg=#005F00
highlight H4Area gui=bold,italic guibg=#BCBCBC guifg=#005F00
highlight Area guifg=#66ff66

" Projects
syn region H1Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H2Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H3Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region H4Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline
syn region Project start="\(\s\|(\)\zs+[0-9]*[A-Za-z]" end="\ze[ \n),.?!;:]" oneline

highlight H1Project gui=bold,underline guibg=#FFD787 guifg=#080808
highlight H2Project gui=bold,underline guibg=#87AFAF guifg=#080808
highlight H3Project gui=bold,underline guibg=#D7AFD7 guifg=#080808
highlight H4Project gui=bold,underline guibg=#BCBCBC guifg=#080808
highlight Project guifg=#FF8700

" Dates
syn match H1Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match H2Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match H3Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match H4Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"
syn match Date "\(2[01][0-9][0-9]-[01][0-9]-[0123][0-9]\|[0-9][0-9][01][0-9][0123][0-9]\(@[0-2][0-9][0-5][0-9]\)\?\)\ze[ \n,.?!;:)]"

highlight H1Date guibg=#FFD787 guifg=#080808 gui=underline
highlight H2Date guibg=#87AFAF guifg=#080808 gui=underline
highlight H3Date guibg=#D7AFD7 guifg=#080808 gui=underline
highlight H4Date guibg=#BCBCBC guifg=#080808 gui=underline
highlight Date gui=underline

" ZIDs (ex: 240112#00)
syn match ZID "[0-9][0-9][01][0-9][0123][0-9]#[A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9]\?\ze[ \n,.?!;:)]"
highlight ZID gui=underline

" ZID Links
syn match ZIDLink "\[[0-9][0-9][01][0-9][0123][0-9]#[A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9][A-HJ-NP-Za-ikm-z0-9]\?\]\ze[ \n,.?!;:)]"
highlight ZIDLink guifg=#87FFD7

" Local Page Links (ex: [[foobar]])
syn region H1PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region H2PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region H3PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region H4PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
syn region PageLink start="\(^\|\s\|(\|::\)\zs\[\[" end="\]\]" contains=@NoSpell oneline
highlight H1PageLink gui=bold guibg=#FFD787 guifg=#333333
highlight H2PageLink gui=bold guibg=#87AFAF guifg=#333333
highlight H3PageLink gui=bold guibg=#D7AFD7 guifg=#333333
highlight H4PageLink gui=bold guibg=#BCBCBC guifg=#333333
highlight PageLink guifg=#00cc00

" Embedded Links [ex: ((baz))]
syn region EmbeddedLink start="\(^\|\s\|(\)\zs((" end="))" contains=@NoSpell oneline
highlight EmbeddedLink guifg=#00ffcc

" ID Links
syn match IDLink "\[#[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
highlight IDLink guifg=#5FFFFF

" Local Links
syn match LocalLink "\[\^[0-9A-Za-z_]\+\]\ze[ \n,.?!;:)]"
highlight LocalLink guifg=#D7FF87

" Ref Links
syn match H1RefLink "\[@[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
syn match H2RefLink "\[@[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
syn match H3RefLink "\[@[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
syn match H4RefLink "\[@[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
syn match RefLink "\[@[A-Za-z0-9_]\+\]\ze[ \n,.?!;:)]"
highlight H1RefLink gui=bold guibg=#FFD787 guifg=#080808
highlight H2RefLink gui=bold guibg=#87AFAF guifg=#080808
highlight H3RefLink gui=bold guibg=#D7AFD7 guifg=#080808
highlight H4RefLink gui=bold guibg=#BCBCBC guifg=#080808
highlight RefLink guifg=#FFFF00

" URL Links
syn match UrlLink "\[![A-Za-z0-9_:%?=/.-]\+\]\ze[ \n,.?!;:)]"
highlight UrlLink guifg=#5FAFFF

" Comments
syn region ZorgComment start="^\s*# " end="$" contains=@zorg oneline
syn region ZorgComment start="^#$" end="$" contains=@zorg oneline
highlight ZorgComment guifg=#808080

" Todos
syn match OpenTodo "^\s*o\s.*\(\n\s\s\+[^o\-*<>].*\)*" contains=@zorg
highlight OpenTodo gui=bold

" Canceled Todos
syn region CanceledTodo start="^\s*\~\s" end="$" contains=@zorg oneline
highlight CanceledTodo gui=italic guifg=#D0D0D0

" Todo Group
syn region TodoGroup start="^\s*\zs>\s" end="$" contains=@zorg oneline
highlight TodoGroup gui=underline

" Blocked Todo
syn region BlockedTodo start="^\s*\zs<\s" end="$" contains=@zorg oneline
highlight BlockedTodo gui=bold guifg=#898782

" Child Todo Bullet
syn region ChildTodoBullet start="^\s*\zs\*\ze\(\s\|$\)" end="\ze\(\s\|$\)" contains=@zorg oneline
highlight ChildTodoBullet gui=bold

" Notes
syn match Note "^\s*\-\s.*\(\n\s\s\+[^o*<>].*\)*" contains=@zorg
highlight Note gui=italic

" Inline Code
syn match InlineCode "`[^`]\+`"
highlight InlineCode guifg=#ffcc99

" Code Blocks
syntax match CodeBlock "^\s\s\+```[a-z]*\n\(\s\s\+.*\n\)*\s\s\+```"
highlight CodeBlock guifg=#ffcc99
