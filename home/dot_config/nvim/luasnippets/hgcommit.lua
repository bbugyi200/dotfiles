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
			{ tag = i(1), design = i(2), bug = i(3), reviewer = i(4, "startblock"), title = i(5) }
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
	-- SNIPPET: s1
	s({ trig = "s1", desc = "Startblock STAGE 1." }, { t("# STAGE 1: "), i(1) }),
	-- SNIPPET: s2
	s({ trig = "s2", desc = "Startblock STAGE 1." }, { t("# STAGE 2: "), i(1) }),
	-- SNIPPET: s3
	s({ trig = "s3", desc = "Startblock STAGE 1." }, { t("# STAGE 3: "), i(1) }),
	-- SNIPPET: s4
	s({ trig = "s4", desc = "Startblock STAGE 1." }, { t("# STAGE 4: "), i(1) }),
	-- SNIPPET: s5
	s({ trig = "s5", desc = "Startblock STAGE 1." }, { t("# STAGE 5: "), i(1) }),
	-- SNIPPET: s6
	s({ trig = "s6", desc = "Startblock STAGE 1." }, { t("# STAGE 6: "), i(1) }),
	-- SNIPPET: s7
	s({ trig = "s7", desc = "Startblock STAGE 1." }, { t("# STAGE 7: "), i(1) }),
	-- SNIPPET: s8
	s({ trig = "s8", desc = "Startblock STAGE 1." }, { t("# STAGE 8: "), i(1) }),
	-- SNIPPET: s9
	s({ trig = "s9", desc = "Startblock STAGE 1." }, { t("# STAGE 9: "), i(1) }),
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
