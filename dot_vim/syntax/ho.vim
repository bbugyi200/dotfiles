" Syntax highlighting for homeorg (.ho) files.

runtime! syntax/txt.vim

syn cluster homeOrgTagRegions add=HomeOrgContext,HomeOrgLink,HomeOrgPragma,HomeOrgProject,HomeOrgProjectBox,HomeOrgRole,HomeOrgWhoContext

syn region HomeOrgLink start="\[\[" end="\]\]" oneline
highlight HomeOrgLink ctermfg=green

syn region HomeOrgContext start="@[A-Za-z]" end="\ze\(\s\|$\)" oneline
syn region HomeOrgWhoContext start="\s\zs[A-Za-z]\+@" end="\ze\(\s\|$\)" oneline
highlight HomeOrgContext ctermfg=red
highlight HomeOrgWhoContext ctermfg=magenta

syn region HomeOrgRole start="\s\zs#[A-Za-z]" end="\ze]\?\(\s\|$\)" oneline
highlight HomeOrgRole ctermfg=darkgreen

syn region HomeOrgProject start="\s\zs+[0-9]*[A-Za-z]" end="\ze\(\s\|$\)" oneline
syn region HomeOrgProjectBox start="\s\zs\[[0-9]*[A-Za-z]" end="]\ze\(\s\|$\)" oneline
highlight HomeOrgProject ctermfg=yellow
highlight HomeOrgProjectBox ctermfg=darkyellow

syn region HomeOrgPragma start="^\s*::\s" end="$" contains=@homeOrgTagRegions oneline
syn region HomeOrgPragma start="^\s*::" end="$" oneline
highlight HomeOrgPragma ctermfg=grey
