" Syntax highlighting for zorq (.zoq) files.

syn region SwogBody start="#\s\zs[SW]\s.*" end="$" containedin=ZorgComment
highlight SwogBody ctermfg=255 ctermbg=red

syn region SWOG start="\s*\zs[SWOG]\ze\s" end="\ze\s" containedin=SwogBody
highlight SWOG ctermfg=white ctermbg=red cterm=standout,underline,bold
