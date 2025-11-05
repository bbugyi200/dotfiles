-- Snippets for fig commits (ex: `hg commit`) live here.

return {
	-- SNIPPET: cl
	s(
		{ trig = "cl", desc = "Full CL message template." },
		fmt(
			[===[
        [{tag}] {title}

        AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT
        BUG={bug}
        MARKDOWN=true
        R={reviewer}
        STARTBLOCK_AUTOSUBMIT=yes
        WANT_LGTM=all
    ]===],
			{ tag = i(1), title = i(2), bug = i(3), reviewer = i(4, "startblock") }
		)
	),
	-- SNIPPET: nosq
	s(
		{ trig = "nosq", desc = "NO_SQ=..." },
		{ t("NO_SQ="), i(1, "1"), t(" unrelated failing test"), i(2), t(": "), i(3) }
	),
	-- SNIPPET: des
	s(
		{ trig = "des", desc = "Link to design doc section." },
		{ t('See the "'), i(1), t('" section of the design doc (go/'), i(2), t(").") }
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
            {cl} has LGTM
            all comments on {cl} are resolved
            # STAGE 2: add reviewer
            and then
            remember
            add reviewer {reviewer}
        ```
    ]===],
			{ cl = i(1), reviewer = i(2) },
			{ repeat_duplicates = true }
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
