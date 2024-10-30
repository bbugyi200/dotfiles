let b:run_cmd = ':Silent plantuml -tpng ' . expand('%:p:r') . '.puml && open ' . expand('%:p:r') . '.png && cliclick kd:cmd kp:tab ku:cmd'
