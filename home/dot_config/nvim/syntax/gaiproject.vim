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

" KICKSTART field name only
syn match GaiProjectKickstartKey "^KICKSTART:" contains=GaiProjectFieldColon
highlight GaiProjectKickstartKey gui=bold guifg=#87D7FF

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

" TAP field - entire line with contains for key highlighting (TAP shares same color as CL)
syn match GaiProjectTAPLine "^TAP:\s*\%(None\)\@!.\+$" contains=GaiProjectTAPKey,GaiProjectURL
syn match GaiProjectTAPKey "^TAP:" contained
syn match GaiProjectTAPNone "^TAP:\s*None\s*$" contains=GaiProjectTAPNoneKey
syn match GaiProjectTAPNoneKey "^TAP:" contained
highlight GaiProjectTAPKey gui=bold guifg=#87D7FF
highlight GaiProjectTAPNoneKey gui=bold guifg=#87D7FF
highlight GaiProjectTAPLine gui=bold guifg=#5FD7FF

" TEST TARGETS field - key line
syn match GaiProjectTestTargetsKey "^TEST TARGETS:" nextgroup=GaiProjectTestTargetsInline skipwhite

" TEST TARGETS - single-line format (one or more valid bazel targets)
" Valid target format: //path/to/package:target_name (FAILED)?
" Path can contain: a-z A-Z 0-9 _ / . -
" Target name can contain: a-z A-Z 0-9 _ -
syn match GaiProjectTestTargetsInline "\s*//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\%( (FAILED)\)\?\%(\s\+//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\%( (FAILED)\)\?\)*\s*$" contained contains=GaiProjectTestTargetFailed

" TEST TARGETS - multi-line format (2-space indented lines, each a valid bazel target)
" Only highlight lines that match the valid bazel target pattern
syn match GaiProjectTestTargetsMultiLine "^\s\s//[a-zA-Z0-9_/.-]\+:[a-zA-Z0-9_-]\+\%( (FAILED)\)\?\s*$" contains=GaiProjectTestTargetFailed

" (FAILED) marker in test targets
syn match GaiProjectTestTargetFailed " (FAILED)" contained

" Highlight groups
highlight GaiProjectTestTargetsKey gui=bold guifg=#87D7FF
highlight GaiProjectTestTargetsInline gui=bold guifg=#AFD75F
highlight GaiProjectTestTargetsMultiLine gui=bold guifg=#AFD75F
highlight GaiProjectTestTargetFailed gui=bold guifg=#FF5F5F

" Field colon
syn match GaiProjectFieldColon ":" contained
highlight GaiProjectFieldColon gui=bold guifg=#808080

" Comments (lines starting with #)
syn region GaiProjectComment start="^\s*# " end="$" oneline
syn region GaiProjectComment start="^#$" end="$" oneline
highlight GaiProjectComment guifg=#808080 gui=italic

" STATUS field - handled with matchgroup to separate key from value highlighting
" Workspace suffix pattern: (project_N) where N is 2-100
syn match GaiProjectStatusBlocked "^STATUS:\s*Blocked" contains=GaiProjectStatusKey
syn match GaiProjectStatusUnstarted "^STATUS:\s*Unstarted" contains=GaiProjectStatusKey
syn match GaiProjectStatusCreatingEZCL "^STATUS:\s*Creating EZ CL\.\.\.\%( ([a-zA-Z0-9_-]\+_\d\+)\)\?" contains=GaiProjectStatusKey,GaiProjectWorkspaceSuffix
syn match GaiProjectStatusCreatingTDDCL "^STATUS:\s*Creating TDD CL\.\.\.\%( ([a-zA-Z0-9_-]\+_\d\+)\)\?" contains=GaiProjectStatusKey,GaiProjectWorkspaceSuffix
syn match GaiProjectStatusRunningQA "^STATUS:\s*Running QA\.\.\.\%( ([a-zA-Z0-9_-]\+_\d\+)\)\?" contains=GaiProjectStatusKey,GaiProjectWorkspaceSuffix
syn match GaiProjectStatusTDDCLCreated "^STATUS:\s*TDD CL Created" contains=GaiProjectStatusKey
syn match GaiProjectStatusFinishingTDDCL "^STATUS:\s*Finishing TDD CL\.\.\.\%( ([a-zA-Z0-9_-]\+_\d\+)\)\?" contains=GaiProjectStatusKey,GaiProjectWorkspaceSuffix
syn match GaiProjectStatusFixingTests "^STATUS:\s*Fixing Tests\.\.\.\%( ([a-zA-Z0-9_-]\+_\d\+)\)\?" contains=GaiProjectStatusKey,GaiProjectWorkspaceSuffix
syn match GaiProjectStatusMakingChangeRequests "^STATUS:\s*Making Change Requests\.\.\.\%( ([a-zA-Z0-9_-]\+_\d\+)\)\?" contains=GaiProjectStatusKey,GaiProjectWorkspaceSuffix
syn match GaiProjectStatusNeedsPresubmit "^STATUS:\s*Needs Presubmit" contains=GaiProjectStatusKey
syn match GaiProjectStatusRunningPresubmits "^STATUS:\s*Running Presubmits\.\.\.\%( ([a-zA-Z0-9_-]\+_\d\+)\)\?" contains=GaiProjectStatusKey,GaiProjectWorkspaceSuffix
syn match GaiProjectStatusNeedsQA "^STATUS:\s*Needs QA" contains=GaiProjectStatusKey
syn match GaiProjectStatusPreMailed "^STATUS:\s*Pre-Mailed" contains=GaiProjectStatusKey
syn match GaiProjectStatusMailed "^STATUS:\s*Mailed" contains=GaiProjectStatusKey
syn match GaiProjectStatusChangesRequested "^STATUS:\s*Changes Requested" contains=GaiProjectStatusKey
syn match GaiProjectStatusSubmitted "^STATUS:\s*Submitted" contains=GaiProjectStatusKey

" Workspace suffix - shown in a dimmed/gray color within STATUS lines
syn match GaiProjectWorkspaceSuffix " ([a-zA-Z0-9_-]\+_\d\+)" contained

" STATUS key pattern (matched within STATUS lines)
syn match GaiProjectStatusKey "^STATUS:" contained

highlight GaiProjectStatusKey gui=bold guifg=#87D7FF
highlight GaiProjectStatusBlocked gui=bold guifg=#D75F00
highlight GaiProjectStatusUnstarted gui=bold guifg=#FFD700
highlight GaiProjectStatusCreatingEZCL gui=bold guifg=#87AFFF
highlight GaiProjectStatusCreatingTDDCL gui=bold guifg=#5F87FF
highlight GaiProjectStatusRunningQA gui=bold guifg=#87AFFF
highlight GaiProjectStatusTDDCLCreated gui=bold guifg=#AF87FF
highlight GaiProjectStatusFinishingTDDCL gui=bold guifg=#5F87FF
highlight GaiProjectStatusFixingTests gui=bold guifg=#87AFFF
highlight GaiProjectStatusMakingChangeRequests gui=bold guifg=#87AFFF
highlight GaiProjectStatusNeedsPresubmit gui=bold guifg=#FFD700
highlight GaiProjectStatusRunningPresubmits gui=bold guifg=#87AFFF
highlight GaiProjectStatusNeedsQA gui=bold guifg=#FFD700
highlight GaiProjectStatusPreMailed gui=bold guifg=#87D700
highlight GaiProjectStatusMailed gui=bold guifg=#00D787
highlight GaiProjectStatusChangesRequested gui=bold guifg=#FFAF00
highlight GaiProjectStatusSubmitted gui=bold guifg=#00AF00
highlight GaiProjectWorkspaceSuffix gui=bold guifg=#808080

" URL pattern (matches http:// or https:// URLs)
syn match GaiProjectURL "https\?://[[:alnum:]._/%-?&=+#:~]\+" contained
highlight GaiProjectURL gui=bold,underline guifg=#569CD6
