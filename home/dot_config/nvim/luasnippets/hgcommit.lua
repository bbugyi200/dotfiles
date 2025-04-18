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
        STARTBLOCK_AUTOSUBMIT=yes
        WANT_LGTM=all
    ]===],
			{ tag = i(1), title = i(2), design = i(3), bug = i(4), reviewer = i(5, "startblock") }
		)
	),
	-- SNIPPET: rap
	s(
		{ trig = "rap", desc = "Startblock condition to wait for 2 rapid/* releases." },
		fmt(
			[===[
        rapid/{release} contains cl/{cl_id} in tag GOLDEN at least 2
    ]===],
			{ release = i(1, "gfpapi"), cl_id = i(2) }
		)
	),
	-- SNIPPET: sb
	s(
		{ trig = "sb", desc = "Startblock section." },
		fmt(
			[===[
        ### Startblock Conditions

        ```
        Startblock:
            # STAGE 1: wait for LGTM on parent CL
            cl/{cl_id} has LGTM
            # STAGE 2: add reviewer
            and then
            add reviewer {reviewer}
        ```
    ]===],
			{ cl_id = i(1), reviewer = i(2) }
		)
	),
	-- SNIPPET: sbe
	s(
		{ trig = "sbe", desc = "Empty Startblock section." },
		fmt(
			[===[
        ### Startblock Conditions

        ```
        Startblock:
            # STAGE 1: {s1}
        ```
    ]===],
			{ s1 = i(1) }
		)
	),
	-- SNIPPET: sN
	s(
		{
			trig = "s([0-9]+)",
			regTrig = true,
			desc = "Startblock STAGE with number.",
		},
		fmt(
			[===[
        # STAGE {num}: {desc}
        and then
        {cond}
    ]===],
			{
				num = f(function(_, snip)
					return snip.captures[1]
				end),
				desc = i(1),
				cond = i(2),
			}
		)
	),
	-- SNIPPET: tags
	s(
		{ trig = "tags", desc = "CL message template tags." },
		fmt(
			[===[
        AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT
        BUG={bug}
        MARKDOWN=true
        R={reviewer}
        STARTBLOCK_AUTOSUBMIT=yes
        WANT_LGTM=all
    ]===],
			{ bug = i(1), reviewer = i(2, "startblock") }
		)
	),
}
