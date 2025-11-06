" Syntax highlighting for gai ProjectSpec files (~/.gai/projects/*.md)

" DESCRIPTION field value (all indented lines following DESCRIPTION:, including blank lines)
" Must be defined first to avoid conflicts with field name matching
syn match GaiProjectDescLine "^\s\s.*$"
highlight GaiProjectDescLine guifg=#D7D7AF

" Field Names - all use same color
syn match GaiProjectFieldName "^\(BUG\|NAME\|DESCRIPTION\|PARENT\|CL\|TEST TARGETS\|STATUS\):" contains=GaiProjectFieldColon
syn match GaiProjectFieldColon ":" contained

highlight GaiProjectFieldName gui=bold guifg=#87D7FF
highlight GaiProjectFieldColon gui=bold guifg=#808080

" BUG field value
syn match GaiProjectBugValue "^BUG:\s*\zs.*$"
highlight GaiProjectBugValue gui=bold guifg=#FF8700

" NAME field value
syn match GaiProjectNameValue "^NAME:\s*\zs.*$"
highlight GaiProjectNameValue gui=bold guifg=#00D7AF

" PARENT field value
syn match GaiProjectParentNone "^PARENT:\s*\zsNone\ze\s*$"
syn match GaiProjectParentValue "^PARENT:\s*\zs[^N].*$"
highlight GaiProjectParentNone gui=italic guifg=#808080
highlight GaiProjectParentValue guifg=#D7AFD7

" CL field value
syn match GaiProjectCLNone "^CL:\s*\zsNone\ze\s*$"
syn match GaiProjectCLValue "^CL:\s*\zs[^N].*$"
highlight GaiProjectCLNone gui=italic guifg=#808080
highlight GaiProjectCLValue guifg=#5FAFFF

" TEST TARGETS field value
syn match GaiProjectTestTargetsNone "^TEST TARGETS:\s*\zsNone\ze\s*$"
syn match GaiProjectTestTargetsValue "^TEST TARGETS:\s*\zs[^N].*$"
highlight GaiProjectTestTargetsNone gui=italic guifg=#808080
highlight GaiProjectTestTargetsValue guifg=#AFD75F

" Comments (lines starting with #)
syn region GaiProjectComment start="^\s*# " end="$" oneline
syn region GaiProjectComment start="^#$" end="$" oneline
highlight GaiProjectComment guifg=#808080 gui=italic

" STATUS field values - match full line with STATUS: and value, defined last for highest priority
syn match GaiProjectStatusNotStarted "^STATUS:.*Not Started.*$"
syn match GaiProjectStatusInProgress "^STATUS:.*In Progress.*$"
syn match GaiProjectStatusTDDCLCreated "^STATUS:.*TDD CL Created.*$"
syn match GaiProjectStatusFixingTests "^STATUS:.*Fixing Tests.*$"
syn match GaiProjectStatusPreMailed "^STATUS:.*Pre-Mailed.*$"
syn match GaiProjectStatusMailed "^STATUS:.*Mailed.*$"
syn match GaiProjectStatusSubmitted "^STATUS:.*Submitted.*$"
syn match GaiProjectStatusFailedCL "^STATUS:.*Failed to Create CL.*$"
syn match GaiProjectStatusFailedTests "^STATUS:.*Failed to Fix Tests.*$"

highlight GaiProjectStatusNotStarted gui=bold guifg=#D7AF00
highlight GaiProjectStatusInProgress gui=bold guifg=#5FD7FF
highlight GaiProjectStatusTDDCLCreated gui=bold guifg=#AF87FF
highlight GaiProjectStatusFixingTests gui=bold guifg=#FFD75F
highlight GaiProjectStatusPreMailed gui=bold guifg=#87D700
highlight GaiProjectStatusMailed gui=bold guifg=#00D787
highlight GaiProjectStatusSubmitted gui=bold guifg=#00AF00
highlight GaiProjectStatusFailedCL gui=bold guifg=#FF5F5F
highlight GaiProjectStatusFailedTests gui=bold guifg=#FF8787
