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

" STATUS field values with different colors - use contains=NONE for highest priority
syn match GaiProjectStatusNotStarted "^STATUS:\s*\zsNot Started\s*$" contains=NONE
syn match GaiProjectStatusInProgress "^STATUS:\s*\zsIn Progress\s*$" contains=NONE
syn match GaiProjectStatusTDDCLCreated "^STATUS:\s*\zsTDD CL Created\s*$" contains=NONE
syn match GaiProjectStatusFixingTests "^STATUS:\s*\zsFixing Tests\s*$" contains=NONE
syn match GaiProjectStatusPreMailed "^STATUS:\s*\zsPre-Mailed\s*$" contains=NONE
syn match GaiProjectStatusMailed "^STATUS:\s*\zsMailed\s*$" contains=NONE
syn match GaiProjectStatusSubmitted "^STATUS:\s*\zsSubmitted\s*$" contains=NONE
syn match GaiProjectStatusFailedCL "^STATUS:\s*\zsFailed to Create CL\s*$" contains=NONE
syn match GaiProjectStatusFailedTests "^STATUS:\s*\zsFailed to Fix Tests\s*$" contains=NONE

highlight link GaiProjectStatusNotStarted GaiProjectStatusNotStartedColor
highlight link GaiProjectStatusInProgress GaiProjectStatusInProgressColor
highlight link GaiProjectStatusTDDCLCreated GaiProjectStatusTDDCLCreatedColor
highlight link GaiProjectStatusFixingTests GaiProjectStatusFixingTestsColor
highlight link GaiProjectStatusPreMailed GaiProjectStatusPreMailedColor
highlight link GaiProjectStatusMailed GaiProjectStatusMailedColor
highlight link GaiProjectStatusSubmitted GaiProjectStatusSubmittedColor
highlight link GaiProjectStatusFailedCL GaiProjectStatusFailedCLColor
highlight link GaiProjectStatusFailedTests GaiProjectStatusFailedTestsColor

highlight GaiProjectStatusNotStartedColor gui=bold guifg=#D7AF00
highlight GaiProjectStatusInProgressColor gui=bold guifg=#5FD7FF
highlight GaiProjectStatusTDDCLCreatedColor gui=bold guifg=#AF87FF
highlight GaiProjectStatusFixingTestsColor gui=bold guifg=#FFD75F
highlight GaiProjectStatusPreMailedColor gui=bold guifg=#87D700
highlight GaiProjectStatusMailedColor gui=bold guifg=#00D787
highlight GaiProjectStatusSubmittedColor gui=bold guifg=#00AF00
highlight GaiProjectStatusFailedCLColor gui=bold guifg=#FF5F5F
highlight GaiProjectStatusFailedTestsColor gui=bold guifg=#FF8787
