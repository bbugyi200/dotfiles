" Syntax highlighting for gai ProjectSpec files (~/.gai/projects/*.md)

" Field Names - each with unique color
syn match GaiProjectFieldBug "^BUG:" contains=GaiProjectFieldColon
syn match GaiProjectFieldName "^NAME:" contains=GaiProjectFieldColon
syn match GaiProjectFieldDescription "^DESCRIPTION:" contains=GaiProjectFieldColon
syn match GaiProjectFieldParent "^PARENT:" contains=GaiProjectFieldColon
syn match GaiProjectFieldCL "^CL:" contains=GaiProjectFieldColon
syn match GaiProjectFieldTestTargets "^TEST TARGETS:" contains=GaiProjectFieldColon
syn match GaiProjectFieldStatus "^STATUS:" contains=GaiProjectFieldColon
syn match GaiProjectFieldColon ":" contained

highlight GaiProjectFieldBug gui=bold guifg=#FF8700
highlight GaiProjectFieldName gui=bold guifg=#00D7AF
highlight GaiProjectFieldDescription gui=bold guifg=#87D7FF
highlight GaiProjectFieldParent gui=bold guifg=#D7AFD7
highlight GaiProjectFieldCL gui=bold guifg=#5FAFFF
highlight GaiProjectFieldTestTargets gui=bold guifg=#FFD75F
highlight GaiProjectFieldStatus gui=bold guifg=#87D700
highlight GaiProjectFieldColon gui=bold guifg=#808080

" BUG field value
syn match GaiProjectBugValue "^BUG:\s*\zs.*$"
highlight GaiProjectBugValue gui=bold guifg=#FF8700

" NAME field value
syn match GaiProjectNameValue "^NAME:\s*\zs.*$"
highlight GaiProjectNameValue gui=bold guifg=#00D7AF

" DESCRIPTION field (indented lines following DESCRIPTION:)
syn region GaiProjectDescription start="^DESCRIPTION:\s*$" end="^\(BUG\|NAME\|DESCRIPTION\|PARENT\|CL\|TEST TARGETS\|STATUS\):\|^$" contains=GaiProjectDescIndent,GaiProjectFieldBug,GaiProjectFieldName,GaiProjectFieldDescription,GaiProjectFieldParent,GaiProjectFieldCL,GaiProjectFieldTestTargets,GaiProjectFieldStatus
syn match GaiProjectDescIndent "^\s\s.*$" contained
highlight GaiProjectDescIndent guifg=#D0D0D0

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

" STATUS field values with different colors
syn match GaiProjectStatusNotStarted "^STATUS:\s*\zsNot Started\ze\s*$"
syn match GaiProjectStatusInProgress "^STATUS:\s*\zsIn Progress\ze\s*$"
syn match GaiProjectStatusTDDCLCreated "^STATUS:\s*\zsTDD CL Created\ze\s*$"
syn match GaiProjectStatusFixingTests "^STATUS:\s*\zsFixing Tests\ze\s*$"
syn match GaiProjectStatusPreMailed "^STATUS:\s*\zsPre-Mailed\ze\s*$"
syn match GaiProjectStatusMailed "^STATUS:\s*\zsMailed\ze\s*$"
syn match GaiProjectStatusSubmitted "^STATUS:\s*\zsSubmitted\ze\s*$"
syn match GaiProjectStatusFailedCL "^STATUS:\s*\zsFailed to Create CL\ze\s*$"
syn match GaiProjectStatusFailedTests "^STATUS:\s*\zsFailed to Fix Tests\ze\s*$"

highlight GaiProjectStatusNotStarted gui=bold guifg=#D7AF00
highlight GaiProjectStatusInProgress gui=bold guifg=#5FD7FF
highlight GaiProjectStatusTDDCLCreated gui=bold guifg=#AF87FF
highlight GaiProjectStatusFixingTests gui=bold guifg=#FFD75F
highlight GaiProjectStatusPreMailed gui=bold guifg=#87D700
highlight GaiProjectStatusMailed gui=bold guifg=#00D787
highlight GaiProjectStatusSubmitted gui=bold guifg=#00AF00
highlight GaiProjectStatusFailedCL gui=bold guifg=#FF5F5F
highlight GaiProjectStatusFailedTests gui=bold guifg=#FF8787

" Comments (lines starting with #)
syn region GaiProjectComment start="^\s*# " end="$" oneline
syn region GaiProjectComment start="^#$" end="$" oneline
highlight GaiProjectComment guifg=#808080 gui=italic
