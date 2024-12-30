local funcs = require("funcs")

if funcs.on_google_machine() then
	return {
		{
			"vim-scripts/vcscommand.vim",
			dependencies = { "vcscommand-g4" },
			cmd = {
				"VCSAdd",
				"VCSAnnotate",
				"VCSBlame",
				"VCSCommit",
				"VCSDelete",
				"VCSDiff",
				"VCSGotoOriginal",
				"VCSInfo",
				"VCSLog",
				"VCSLock",
				"VCSRemove",
				"VCSRevert",
				"VCSReview",
				"VCSStatus",
				"VCSUpdate",
				"VCSUnlock",
				"VCSVimDiff",
			},
		},
	}
else
	return {}
end
