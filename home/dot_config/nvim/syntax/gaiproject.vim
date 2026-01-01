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
" NOTE: "Changes Requested" has been replaced by the COMMENTS field
" Match READY TO MAIL suffix first (more specific pattern)
syn match GaiProjectStatusReadyToMail "^STATUS:\s*Drafted\s*-\s*(!:\s*READY TO MAIL)" contains=GaiProjectStatusKey,GaiProjectReadyToMailSuffix
syn match GaiProjectReadyToMailSuffix "(!:\s*READY TO MAIL)" contained
syn match GaiProjectStatusDrafted "^STATUS:\s*Drafted$" contains=GaiProjectStatusKey
syn match GaiProjectStatusMailed "^STATUS:\s*Mailed" contains=GaiProjectStatusKey
syn match GaiProjectStatusSubmitted "^STATUS:\s*Submitted" contains=GaiProjectStatusKey
syn match GaiProjectStatusReverted "^STATUS:\s*Reverted" contains=GaiProjectStatusKey

" STATUS key pattern (matched within STATUS lines)
syn match GaiProjectStatusKey "^STATUS:" contained

highlight GaiProjectStatusKey gui=bold guifg=#87D7FF
highlight GaiProjectStatusDrafted gui=bold guifg=#87D700
highlight GaiProjectStatusMailed gui=bold guifg=#00D787
highlight GaiProjectStatusSubmitted gui=bold guifg=#00AF00
highlight GaiProjectStatusReverted gui=bold guifg=#808080
" READY TO MAIL suffix - use same red background as other error suffixes
highlight GaiProjectStatusReadyToMail gui=bold guifg=#87D700
highlight GaiProjectReadyToMailSuffix gui=bold guifg=#FFFFFF guibg=#AF0000

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

" COMMITS field - tracks commit/amend history for the ChangeSpec
" Key line
syn match GaiProjectCommitsKey "^COMMITS:"
" Regular entry lines: (N) Note text (2-space indented)
syn match GaiProjectCommitsEntry "^\s\s(\d\+)\s.\+$" contains=GaiProjectCommitsNumber,GaiProjectCommitsSuffixError,GaiProjectCommitsSuffixRunningAgent,GaiProjectCommitsSuffixRunningAgentEmpty,GaiProjectCommitsSuffixRunningProcess,GaiProjectCommitsSuffixKilledProcess
syn match GaiProjectCommitsNumber "(\d\+)" contained
" Proposed entry lines: (Na) Note text (2-space indented, where 'a' is a-z)
syn match GaiProjectCommitsProposedEntry "^\s\s(\d\+[a-z])\s.\+$" contains=GaiProjectCommitsProposedNumber,GaiProjectCommitsSuffixError,GaiProjectCommitsSuffixRunningAgent,GaiProjectCommitsSuffixRunningAgentEmpty,GaiProjectCommitsSuffixRunningProcess,GaiProjectCommitsSuffixKilledProcess
syn match GaiProjectCommitsProposedNumber "(\d\+[a-z])" contained
" Suffix patterns for COMMITS entry lines
" (!: <msg>) = error suffix with red background for maximum visibility
" (@: <msg>) = running agent suffix with orange background (same as @@@ query)
" (@) = running agent suffix without message (same as @@@ query)
" ($: <PID>) = running process suffix with yellow background ($$$ query)
" (~$: <PID>) = killed process suffix with faded grayish-yellow background
syn match GaiProjectCommitsSuffixError "(!:\s*[^)]\+)" contained
syn match GaiProjectCommitsSuffixRunningAgent "(@:\s*[^)]\+)" contained
syn match GaiProjectCommitsSuffixRunningAgentEmpty "(@)" contained
syn match GaiProjectCommitsSuffixRunningProcess "(\$:\s*[^)]\+)" contained
syn match GaiProjectCommitsSuffixKilledProcess "(\~\$:\s*[^)]\+)" contained
" CHAT and DIFF sub-fields (6-space indented with | prefix)
syn match GaiProjectCommitsChatLine "^\s\{6\}|\s*CHAT:\s*.\+$" contains=GaiProjectCommitsSubfieldPipe,GaiProjectCommitsChatKey,GaiProjectCommitsPath,GaiProjectCommitsChatDuration
syn match GaiProjectCommitsDiffLine "^\s\{6\}|\s*DIFF:\s*.\+$" contains=GaiProjectCommitsSubfieldPipe,GaiProjectCommitsDiffKey,GaiProjectCommitsPath
syn match GaiProjectCommitsSubfieldPipe "|" contained
syn match GaiProjectCommitsChatKey "CHAT:" contained
syn match GaiProjectCommitsDiffKey "DIFF:" contained
syn match GaiProjectCommitsPath "\~\?/[[:alnum:]._/-]\+" contained
syn match GaiProjectCommitsChatDuration "(\d\+[hms]\+[^)]*)" contained
highlight GaiProjectCommitsKey gui=bold guifg=#87D7FF
highlight GaiProjectCommitsEntry guifg=#D7D7AF
highlight GaiProjectCommitsNumber gui=bold guifg=#D7AF5F
highlight GaiProjectCommitsProposedEntry guifg=#D7D7AF
highlight GaiProjectCommitsProposedNumber gui=bold guifg=#D7AF5F
highlight GaiProjectCommitsChatLine guifg=#87AFFF
highlight GaiProjectCommitsDiffLine guifg=#87AFFF
highlight GaiProjectCommitsSubfieldPipe guifg=#808080
highlight GaiProjectCommitsChatKey gui=bold guifg=#87D7FF
highlight GaiProjectCommitsDiffKey gui=bold guifg=#87D7FF
highlight GaiProjectCommitsPath guifg=#87AFFF
highlight GaiProjectCommitsChatDuration guifg=#808080
highlight GaiProjectCommitsSuffixError gui=bold guifg=#FFFFFF guibg=#AF0000
highlight GaiProjectCommitsSuffixRunningAgent gui=bold guifg=#FFFFFF guibg=#FF8C00
highlight GaiProjectCommitsSuffixRunningAgentEmpty gui=bold guifg=#FFFFFF guibg=#FF8C00
highlight GaiProjectCommitsSuffixRunningProcess gui=bold guifg=#000000 guibg=#FFD700
highlight GaiProjectCommitsSuffixKilledProcess gui=bold guifg=#000000 guibg=#8B8000

" HOOKS field - tracks hook commands and their execution status
" Key line
syn match GaiProjectHooksKey "^HOOKS:"
" Command lines (2-space indented, not starting with [ or ()
syn match GaiProjectHooksCommand "^\s\s[^\[()].*$"
" Status lines (4-space indented)
" New format: (N) or (Na) [YYmmdd_HHMMSS] STATUS (XmYs)
" Old format: [YYmmdd_HHMMSS] STATUS (XmYs)
syn match GaiProjectHooksStatusLine "^\s\{4\}(\d\+[a-z]\?)\s*\[\d\{6\}_\d\{6\}\]\s*\%(RUNNING\|PASSED\|FAILED\|ZOMBIE\).*$" contains=GaiProjectHooksEntryNum,GaiProjectHooksTimestamp,GaiProjectHooksPassed,GaiProjectHooksFailed,GaiProjectHooksRunning,GaiProjectHooksZombie,GaiProjectHooksDuration,GaiProjectHooksSuffixError,GaiProjectHooksSuffixTimestamp,GaiProjectHooksSuffixRunningAgent,GaiProjectHooksSuffixRunningAgentEmpty,GaiProjectHooksSuffixRunningProcess,GaiProjectHooksSuffixKilledProcess
syn match GaiProjectHooksStatusLineOld "^\s\{4\}\[\d\{6\}_\d\{6\}\]\s*\%(RUNNING\|PASSED\|FAILED\|ZOMBIE\).*$" contains=GaiProjectHooksTimestamp,GaiProjectHooksPassed,GaiProjectHooksFailed,GaiProjectHooksRunning,GaiProjectHooksZombie,GaiProjectHooksDuration,GaiProjectHooksSuffixError,GaiProjectHooksSuffixTimestamp,GaiProjectHooksSuffixRunningAgent,GaiProjectHooksSuffixRunningAgentEmpty,GaiProjectHooksSuffixRunningProcess,GaiProjectHooksSuffixKilledProcess
syn match GaiProjectHooksEntryNum "(\d\+[a-z]\?)" contained
syn match GaiProjectHooksTimestamp "\[\d\{6\}_\d\{6\}\]" contained
syn match GaiProjectHooksPassed "PASSED" contained
syn match GaiProjectHooksFailed "FAILED" contained
syn match GaiProjectHooksRunning "RUNNING" contained
syn match GaiProjectHooksZombie "ZOMBIE" contained
syn match GaiProjectHooksDuration "(\d\+[hms]\+[^)]*)" contained
" Suffix patterns for hook status lines
" (!: <msg>) = error suffix with red background for maximum visibility
" (@: <msg>) = running agent suffix with orange background (same as @@@ query)
" (@) = running agent suffix without message (same as @@@ query)
" ($: <PID>) = running process suffix with yellow background ($$$ query)
" (~$: <PID>) = killed process suffix with faded grayish-yellow background
" (YYmmdd_HHMMSS) = timestamp suffix (pink foreground) - legacy, now uses @:
syn match GaiProjectHooksSuffixError "(!:\s*[^)]\+)" contained
syn match GaiProjectHooksSuffixRunningAgent "(@:\s*[^)]\+)" contained
syn match GaiProjectHooksSuffixRunningAgentEmpty "(@)" contained
syn match GaiProjectHooksSuffixRunningProcess "(\$:\s*[^)]\+)" contained
syn match GaiProjectHooksSuffixKilledProcess "(\~\$:\s*[^)]\+)" contained
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
highlight GaiProjectHooksSuffixError gui=bold guifg=#FFFFFF guibg=#AF0000
highlight GaiProjectHooksSuffixRunningAgent gui=bold guifg=#FFFFFF guibg=#FF8C00
highlight GaiProjectHooksSuffixRunningAgentEmpty gui=bold guifg=#FFFFFF guibg=#FF8C00
highlight GaiProjectHooksSuffixRunningProcess gui=bold guifg=#000000 guibg=#FFD700
highlight GaiProjectHooksSuffixKilledProcess gui=bold guifg=#000000 guibg=#8B8000
highlight GaiProjectHooksSuffixTimestamp gui=bold guifg=#D75F87

" COMMENTS field - tracks Critique code review comments
" Key line
syn match GaiProjectCommentsKey "^COMMENTS:"
" Entry lines: [reviewer] path or [reviewer] path - (suffix)
" 2-space indented lines starting with [
syn match GaiProjectCommentsEntry "^\s\s\[[^\]]\+\]\s.\+$" contains=GaiProjectCommentsReviewer,GaiProjectCommentsPath,GaiProjectCommentsSuffixError,GaiProjectCommentsSuffixTimestamp,GaiProjectCommentsSuffixRunningAgent,GaiProjectCommentsSuffixRunningAgentEmpty
syn match GaiProjectCommentsReviewer "\[[^\]]\+\]" contained
syn match GaiProjectCommentsPath "\~\?/[[:alnum:]._/-]\+\.json" contained
" Suffix patterns for comment entries (only highlight content in parens, not the dash)
" (!: <msg>) = error suffix with red background for maximum visibility
"   e.g., (!: ZOMBIE), (!: Unresolved Critique Comments)
" (@: <msg>) = running agent suffix with orange background (same as @@@ query)
" (@) = running agent suffix without message (same as @@@ query)
" (YYmmdd_HHMMSS) = timestamp suffix, CRS running (pink foreground) - legacy, now uses @:
syn match GaiProjectCommentsSuffixError "(!:\s*[^)]\+)" contained
syn match GaiProjectCommentsSuffixRunningAgent "(@:\s*[^)]\+)" contained
syn match GaiProjectCommentsSuffixRunningAgentEmpty "(@)" contained
syn match GaiProjectCommentsSuffixTimestamp "(\d\{6\}_\d\{6\})" contained
highlight GaiProjectCommentsKey gui=bold guifg=#87D7FF
highlight GaiProjectCommentsEntry guifg=#D7D7AF
highlight GaiProjectCommentsReviewer gui=bold guifg=#D7AF5F
highlight GaiProjectCommentsPath guifg=#87AFFF
highlight GaiProjectCommentsSuffixError gui=bold guifg=#FFFFFF guibg=#AF0000
highlight GaiProjectCommentsSuffixRunningAgent gui=bold guifg=#FFFFFF guibg=#FF8C00
highlight GaiProjectCommentsSuffixRunningAgentEmpty gui=bold guifg=#FFFFFF guibg=#FF8C00
highlight GaiProjectCommentsSuffixTimestamp gui=bold guifg=#D75F87

" URL pattern (matches http:// or https:// URLs)
syn match GaiProjectURL "https\?://[[:alnum:]._/%-?&=+#:~]\+" contained
highlight GaiProjectURL gui=bold,underline guifg=#569CD6
