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

" RUNNING field - tracks active workflows claiming workspaces
" Key line
syn match GaiProjectRunningKey "^RUNNING:"
" Multi-line format (2-space indented lines with format: #N | WORKFLOW | CL_NAME)
syn match GaiProjectRunningLine "^\s\s#\d\+\s*|.\+$" contains=GaiProjectRunningWorkspaceNum,GaiProjectRunningPipe
syn match GaiProjectRunningWorkspaceNum "#\d\+" contained
syn match GaiProjectRunningPipe "|" contained
highlight GaiProjectRunningKey gui=bold guifg=#87D7FF
highlight GaiProjectRunningLine guifg=#87AFFF
highlight GaiProjectRunningWorkspaceNum gui=bold guifg=#FFD700
highlight GaiProjectRunningPipe guifg=#808080

" STATUS field - handled with matchgroup to separate key from value highlighting
" NOTE: Keep in sync with VALID_STATUSES in home/lib/gai/status_state_machine.py
syn match GaiProjectStatusDrafted "^STATUS:\s*Drafted" contains=GaiProjectStatusKey
syn match GaiProjectStatusMailed "^STATUS:\s*Mailed" contains=GaiProjectStatusKey
syn match GaiProjectStatusChangesRequested "^STATUS:\s*Changes Requested" contains=GaiProjectStatusKey
syn match GaiProjectStatusSubmitted "^STATUS:\s*Submitted" contains=GaiProjectStatusKey
syn match GaiProjectStatusReverted "^STATUS:\s*Reverted" contains=GaiProjectStatusKey

" STATUS key pattern (matched within STATUS lines)
syn match GaiProjectStatusKey "^STATUS:" contained

highlight GaiProjectStatusKey gui=bold guifg=#87D7FF
highlight GaiProjectStatusDrafted gui=bold guifg=#87D700
highlight GaiProjectStatusMailed gui=bold guifg=#00D787
highlight GaiProjectStatusChangesRequested gui=bold guifg=#FFAF00
highlight GaiProjectStatusSubmitted gui=bold guifg=#00AF00
highlight GaiProjectStatusReverted gui=bold guifg=#808080

" PRESUBMIT field - entire line with contains for key and tag highlighting
syn match GaiProjectPresubmitLine "^PRESUBMIT:\s*.\+$" contains=GaiProjectPresubmitKey,GaiProjectPresubmitPassed,GaiProjectPresubmitFailed,GaiProjectPresubmitZombie
syn match GaiProjectPresubmitKey "^PRESUBMIT:" contained
syn match GaiProjectPresubmitPassed "(PASSED)" contained
syn match GaiProjectPresubmitFailed "(FAILED)" contained
syn match GaiProjectPresubmitZombie "(ZOMBIE)" contained
highlight GaiProjectPresubmitKey gui=bold guifg=#87D7FF
highlight GaiProjectPresubmitLine guifg=#AF87D7
highlight GaiProjectPresubmitPassed gui=bold guifg=#00AF00
highlight GaiProjectPresubmitFailed gui=bold guifg=#FF5F5F
highlight GaiProjectPresubmitZombie gui=bold guifg=#FFAF00

" HISTORY field - tracks commit/amend history for the ChangeSpec
" Key line
syn match GaiProjectHistoryKey "^HISTORY:"
" Regular entry lines: (N) Note text (2-space indented)
syn match GaiProjectHistoryEntry "^\s\s(\d\+)\s.\+$" contains=GaiProjectHistoryNumber
syn match GaiProjectHistoryNumber "(\d\+)" contained
" Proposed entry lines: (Na) Note text (2-space indented, where 'a' is a-z)
syn match GaiProjectHistoryProposedEntry "^\s\s(\d\+[a-z])\s.\+$" contains=GaiProjectHistoryProposedNumber
syn match GaiProjectHistoryProposedNumber "(\d\+[a-z])" contained
" CHAT and DIFF sub-fields (6-space indented with | prefix)
syn match GaiProjectHistoryChatLine "^\s\{6\}|\s*CHAT:\s*.\+$" contains=GaiProjectHistoryChatKey,GaiProjectHistoryPath
syn match GaiProjectHistoryDiffLine "^\s\{6\}|\s*DIFF:\s*.\+$" contains=GaiProjectHistoryDiffKey,GaiProjectHistoryPath
syn match GaiProjectHistoryChatKey "CHAT:" contained
syn match GaiProjectHistoryDiffKey "DIFF:" contained
syn match GaiProjectHistoryPath "\~\?/[[:alnum:]._/-]\+" contained
highlight GaiProjectHistoryKey gui=bold guifg=#87D7FF
highlight GaiProjectHistoryEntry guifg=#D7D7AF
highlight GaiProjectHistoryNumber gui=bold guifg=#D7AF5F
highlight GaiProjectHistoryProposedEntry guifg=#D7D7AF
highlight GaiProjectHistoryProposedNumber gui=bold guifg=#D7AF5F
highlight GaiProjectHistoryChatLine guifg=#87AFFF
highlight GaiProjectHistoryDiffLine guifg=#87AFFF
highlight GaiProjectHistoryChatKey gui=bold guifg=#87AFFF
highlight GaiProjectHistoryDiffKey gui=bold guifg=#87AFFF
highlight GaiProjectHistoryPath guifg=#87AFFF

" HOOKS field - tracks hook commands and their execution status
" Key line
syn match GaiProjectHooksKey "^HOOKS:"
" Command lines (2-space indented, not starting with [ or ()
syn match GaiProjectHooksCommand "^\s\s[^\[()].*$"
" Status lines (4-space indented)
" New format: (N) or (Na) [YYmmdd_HHMMSS] STATUS (XmYs)
" Old format: [YYmmdd_HHMMSS] STATUS (XmYs)
syn match GaiProjectHooksStatusLine "^\s\{4\}(\d\+[a-z]\?)\s*\[\d\{6\}_\d\{6\}\]\s*\%(RUNNING\|PASSED\|FAILED\|ZOMBIE\).*$" contains=GaiProjectHooksEntryNum,GaiProjectHooksTimestamp,GaiProjectHooksPassed,GaiProjectHooksFailed,GaiProjectHooksRunning,GaiProjectHooksZombie,GaiProjectHooksDuration,GaiProjectHooksSuffixZombie,GaiProjectHooksSuffixTimestamp
syn match GaiProjectHooksStatusLineOld "^\s\{4\}\[\d\{6\}_\d\{6\}\]\s*\%(RUNNING\|PASSED\|FAILED\|ZOMBIE\).*$" contains=GaiProjectHooksTimestamp,GaiProjectHooksPassed,GaiProjectHooksFailed,GaiProjectHooksRunning,GaiProjectHooksZombie,GaiProjectHooksDuration,GaiProjectHooksSuffixZombie,GaiProjectHooksSuffixTimestamp
syn match GaiProjectHooksEntryNum "(\d\+[a-z]\?)" contained
syn match GaiProjectHooksTimestamp "\[\d\{6\}_\d\{6\}\]" contained
syn match GaiProjectHooksPassed "PASSED" contained
syn match GaiProjectHooksFailed "FAILED" contained
syn match GaiProjectHooksRunning "RUNNING" contained
syn match GaiProjectHooksZombie "ZOMBIE" contained
syn match GaiProjectHooksDuration "(\d\+[hms]\+[^)]*)" contained
" Suffix patterns for hook status lines
" (!) or (ZOMBIE) = zombie/stale hook suffix (red foreground)
" (YYmmdd_HHMMSS) = timestamp suffix (pink foreground)
syn match GaiProjectHooksSuffixZombie "(!)" contained
syn match GaiProjectHooksSuffixZombie "(ZOMBIE)" contained
syn match GaiProjectHooksSuffixTimestamp "(\d\{6\}_\d\{6\})" contained
highlight GaiProjectHooksKey gui=bold guifg=#87D7FF
highlight GaiProjectHooksCommand guifg=#D7D7AF
highlight GaiProjectHooksStatusLine guifg=#6C7086
highlight GaiProjectHooksStatusLineOld guifg=#6C7086
highlight GaiProjectHooksEntryNum gui=bold guifg=#D7AF5F
highlight GaiProjectHooksTimestamp guifg=#AF87D7
highlight GaiProjectHooksPassed gui=bold guifg=#00AF00
highlight GaiProjectHooksFailed gui=bold guifg=#FF5F5F
highlight GaiProjectHooksRunning gui=bold guifg=#87AFFF
highlight GaiProjectHooksZombie gui=bold guifg=#FFAF00
highlight GaiProjectHooksDuration guifg=#D7AF5F
highlight GaiProjectHooksSuffixZombie gui=bold guifg=#AF0000
highlight GaiProjectHooksSuffixTimestamp gui=bold guifg=#D75F87

" URL pattern (matches http:// or https:// URLs)
syn match GaiProjectURL "https\?://[[:alnum:]._/%-?&=+#:~]\+" contained
highlight GaiProjectURL gui=bold,underline guifg=#569CD6
