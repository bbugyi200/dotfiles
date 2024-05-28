" Syntax highlighting for zorq (.zoq) files.

syn region SwogBody start="#\s\zs[SW]\s.*" end="$" containedin=ZorgComment
highlight SwogBody ctermfg=red cterm=bold

syn region SWOG start="\s*\zs[SWOG]\ze\s" end="\ze\s" containedin=SwogBody
highlight SWOG ctermfg=red ctermbg=white cterm=standout,underline,bold
