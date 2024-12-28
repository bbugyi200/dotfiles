" Syntax highlighting for zorq (.zoq) files.

syn region SwogBody start="#\s\zs[SWOG]\s[^=].*" end="$" containedin=ZorgComment
highlight SwogBody guifg=#ffffff guibg=#ff8c1a

syn region SWOG start="\s*\zs[SWOG]\ze\s[^=]" end="\ze\s[^=]" containedin=SwogBody
highlight SWOG guifg=#ff8c1a guibg=#ffffff gui=standout,underline,bold
