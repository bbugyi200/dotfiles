" Syntax highlighting for zorq (.zoq) files.

syn region SwogBody start="#\s\zs[SW]\s.*" end="$" containedin=ZorgComment
highlight SwogBody ctermfg=255 ctermbg=darkblue

syn region SWOG start="\s*\zs[SWOG]\ze\s" end="\ze\s" containedin=SwogBody
highlight SWOG ctermfg=white ctermbg=darkblue cterm=standout,underline,bold
