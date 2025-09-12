" Vim universal .txt syntax file ErrorMsg

syn cluster txtContains add=Todo,BeginWS,Underlined,WildMenu

" Section
" syn match Statement "^[A-Z][^a-z]*[A-Z0-9)\]]$" contains=@txtContains,@NoSpell
" OLD --> [A-Z () 0-9 / \[\] : # -]

" Title
syn region WildMenu start="###" end="###$" contains=@NoSpell oneline

" Subsection
syn region Type start="^\s*===" end="===$" contains=@NoSpell oneline

" Subsubsection
syn region Function start="^\s*---" end="---$" contains=@NoSpell oneline

" Bullets
" syn match ModeMsg "^\s*\([*-]\|[A-Za-z0-9]\.\)" contains=@NoSpell

" Web Links
syn match Underlined "http\S*" contains=@NoSpell,EndP

" Comments
syn region Comment start="\/\/ " end="$" contains=@txtContains,@NoSpell oneline
syn region Comment start="^\s*# " end="$" contains=@txtContains,@NoSpell oneline
syn region Comment start="^#$" end="$" contains=@txtContains,@NoSpell oneline

" Highlights
" 'keepend' prevents contains items from extending the outer item
syn keyword Todo TODO NOTE FIXME

syn region Todo start="<\[" end="\]>" oneline
" syn region ErrorMsg start="{" end="}" oneline
