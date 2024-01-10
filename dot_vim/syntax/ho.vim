" Syntax highlighting for homeorg (.ho) files.

runtime! syntax/txt.vim

syn region HomeOrgLink start="\[\[" end="\]\]" oneline
highlight HomeOrgLink ctermfg=green

syn region HomeOrgContext start="@[A-Za-z]" end="\ze\(\s\|$\)" oneline
syn region HomeOrgWhoContext start="\s\zs[A-Za-z]\+@" end="\ze\(\s\|$\)" oneline
highlight HomeOrgContext ctermfg=black ctermbg=lightred
highlight HomeOrgWhoContext ctermfg=lightgrey ctermbg=darkblue

syn region HomeOrgRole start="\s\zs#[A-Za-z]" end="\ze]\?\(\s\|$\)" oneline
highlight HomeOrgRole ctermfg=darkgreen

syn region HomeOrgProject start="\s\zs+[A-Za-z]" end="\ze\(\s\|$\)" oneline
syn region HomeOrgProjectBox start="\s\zs\[[A-Za-z]" end="]\ze\(\s\|$\)" oneline
highlight HomeOrgProject ctermfg=yellow
highlight HomeOrgProjectBox ctermfg=darkyellow
