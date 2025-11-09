" Syntax highlighting for gai ProjectSpec files (~/.gai/projects/*.md)

" DESCRIPTION field value (all indented lines following DESCRIPTION:, including blank lines)
" Must be defined first to avoid conflicts with field name matching
syn match GaiProjectDescLine "^\s\s.*$"
highlight GaiProjectDescLine guifg=#D7D7AF

" BUG field - entire line with contains for key highlighting (BUG and CL share same color)
syn match GaiProjectBugLine "^BUG:\s*\%(None\)\@!.\+$" contains=GaiProjectBugKey,GaiProjectURL
syn match GaiProjectBugKey "^BUG:" contained
syn match GaiProjectBugNone "^BUG:\s*None\s*$" contains=GaiProjectBugNoneKey
syn match GaiProjectBugNoneKey "^BUG:" contained
highlight GaiProjectBugKey gui=bold guifg=#87D7FF
highlight GaiProjectBugNoneKey gui=bold guifg=#87D7FF
highlight GaiProjectBugLine gui=bold guifg=#5FD7FF

" NAME field - entire line with contains for key highlighting (NAME and PARENT share same color)
syn match GaiProjectNameLine "^NAME:\s*\%(None\)\@!.\+$" contains=GaiProjectNameKey
syn match GaiProjectNameKey "^NAME:" contained
syn match GaiProjectNameNone "^NAME:\s*None\s*$" contains=GaiProjectNameNoneKey
syn match GaiProjectNameNoneKey "^NAME:" contained
highlight GaiProjectNameKey gui=bold guifg=#87D7FF
highlight GaiProjectNameNoneKey gui=bold guifg=#87D7FF
highlight GaiProjectNameLine gui=bold guifg=#00D7AF

" DESCRIPTION field name only
syn match GaiProjectDescriptionKey "^DESCRIPTION:" contains=GaiProjectFieldColon
highlight GaiProjectDescriptionKey gui=bold guifg=#87D7FF

" PARENT field - entire line with contains for key highlighting (NAME and PARENT share same color)
syn match GaiProjectParentLine "^PARENT:\s*\%(None\)\@!.\+$" contains=GaiProjectParentKey
syn match GaiProjectParentKey "^PARENT:" contained
syn match GaiProjectParentNone "^PARENT:\s*None\s*$" contains=GaiProjectParentNoneKey
syn match GaiProjectParentNoneKey "^PARENT:" contained
highlight GaiProjectParentKey gui=bold guifg=#87D7FF
highlight GaiProjectParentNoneKey gui=bold guifg=#87D7FF
highlight GaiProjectParentLine gui=bold guifg=#00D7AF

" CL field - entire line with contains for key highlighting (BUG and CL share same color)
syn match GaiProjectCLLine "^CL:\s*\%(None\)\@!.\+$" contains=GaiProjectCLKey,GaiProjectURL
syn match GaiProjectCLKey "^CL:" contained
syn match GaiProjectCLNone "^CL:\s*None\s*$" contains=GaiProjectCLNoneKey
syn match GaiProjectCLNoneKey "^CL:" contained
highlight GaiProjectCLKey gui=bold guifg=#87D7FF
highlight GaiProjectCLNoneKey gui=bold guifg=#87D7FF
highlight GaiProjectCLLine gui=bold guifg=#5FD7FF

" TEST TARGETS field - key line
syn match GaiProjectTestTargetsKey "^TEST TARGETS:" nextgroup=GaiProjectTestTargetsInline skipwhite

" TEST TARGETS - single-line format (one or more valid bazel targets)
" Valid target format: //path/to/package:target_name
" Path can contain: a-z A-Z 0-9 _ / . -
" Target name can contain: a-z A-Z 0-9 _ -
syn match GaiProjectTestTargetsInline "\s*//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\%(\s\+//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\)*\s*$" contained

" TEST TARGETS - multi-line format (2-space indented lines, each a valid bazel target)
" Only highlight lines that match the valid bazel target pattern
syn match GaiProjectTestTargetsMultiLine "^\s\s//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\s*$"

" Highlight groups
highlight GaiProjectTestTargetsKey gui=bold guifg=#87D7FF
highlight GaiProjectTestTargetsInline gui=bold guifg=#AFD75F
highlight GaiProjectTestTargetsMultiLine gui=bold guifg=#AFD75F

" Field colon
syn match GaiProjectFieldColon ":" contained
highlight GaiProjectFieldColon gui=bold guifg=#808080

" Comments (lines starting with #)
syn region GaiProjectComment start="^\s*# " end="$" oneline
syn region GaiProjectComment start="^#$" end="$" oneline
highlight GaiProjectComment guifg=#808080 gui=italic

" STATUS field - handled with matchgroup to separate key from value highlighting
syn match GaiProjectStatusBlocked "^STATUS:\s*Blocked" contains=GaiProjectStatusKey
syn match GaiProjectStatusNotStarted "^STATUS:\s*Not Started" contains=GaiProjectStatusKey
syn match GaiProjectStatusInProgress "^STATUS:\s*In Progress" contains=GaiProjectStatusKey
syn match GaiProjectStatusTDDCLCreated "^STATUS:\s*TDD CL Created" contains=GaiProjectStatusKey
syn match GaiProjectStatusFixingTests "^STATUS:\s*Fixing Tests" contains=GaiProjectStatusKey
syn match GaiProjectStatusPreMailed "^STATUS:\s*Pre-Mailed" contains=GaiProjectStatusKey
syn match GaiProjectStatusMailed "^STATUS:\s*Mailed" contains=GaiProjectStatusKey
syn match GaiProjectStatusSubmitted "^STATUS:\s*Submitted" contains=GaiProjectStatusKey
syn match GaiProjectStatusFailedCL "^STATUS:\s*Failed to Create CL" contains=GaiProjectStatusKey
syn match GaiProjectStatusFailedTests "^STATUS:\s*Failed to Fix Tests" contains=GaiProjectStatusKey

" STATUS key pattern (matched within STATUS lines)
syn match GaiProjectStatusKey "^STATUS:" contained

highlight GaiProjectStatusKey gui=bold guifg=#87D7FF
highlight GaiProjectStatusBlocked gui=bold guifg=#AF5F00
highlight GaiProjectStatusNotStarted gui=bold guifg=#D7AF00
highlight GaiProjectStatusInProgress gui=bold guifg=#5FD7FF
highlight GaiProjectStatusTDDCLCreated gui=bold guifg=#AF87FF
highlight GaiProjectStatusFixingTests gui=bold guifg=#FFD75F
highlight GaiProjectStatusPreMailed gui=bold guifg=#87D700
highlight GaiProjectStatusMailed gui=bold guifg=#00D787
highlight GaiProjectStatusSubmitted gui=bold guifg=#00AF00
highlight GaiProjectStatusFailedCL gui=bold guifg=#FF5F5F
highlight GaiProjectStatusFailedTests gui=bold guifg=#FF8787

" URL pattern (matches http:// or https:// URLs)
syn match GaiProjectURL "https\?://[[:alnum:]._/%-?&=+#:~]\+" contained
highlight GaiProjectURL gui=bold,underline guifg=#569CD6
