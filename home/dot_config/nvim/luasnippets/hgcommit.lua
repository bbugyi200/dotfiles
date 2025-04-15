-- Snippets for fig commits (ex: `hg commit`) live here.

return {
	-- SNIPPET: cl
	s(
		{ trig = "cl", desc = "Full CL message template." },
		fmt(
			[===[
        [{tag}] {title}

        design: go/{design}

        AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT
        BUG={bug}
        MARKDOWN=true
        R={reviewer}
        WANT_LGTM=all
    ]===],
			{ tag = i(1), design = i(2), bug = i(3), reviewer = i(4, "startblock"), title = i(5) }
		)
	),
}
