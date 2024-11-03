let b:puml_png = expand('%:p:r') . '.png'
let b:run_cmd = ':Silent plantuml -tpng ' . expand('%:p:r') . '.puml && open ' . b:puml_png . ' && cliclick kd:cmd kp:tab ku:cmd && mac_copy_png ' . b:puml_png . ' && echo Copied'
