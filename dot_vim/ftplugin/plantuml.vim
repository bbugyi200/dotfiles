let b:run_cmd = ':Silent plantuml -tpng ' . expand('%:p') . ' && open ' . expand('%:p:r') . '.png'
