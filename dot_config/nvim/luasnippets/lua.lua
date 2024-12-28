return {
	-- i
	s({ trig = "i", desc = "A LuaSnip insertNode", hidden = true }, { t("i("), i(1, "1"), t(', "'), i(2), t('")') }),
	-- s
	s(
		{ trig = "s", desc = "A LuaSnip snippet", hidden = true },
		fmta(
			[[
  -- <trig>
  s(
    { trig = "<trig>", desc = "<desc>"<autosnippet> },
    { <rhs> }
  ),
  ]],
			{
				trig = i(1, "foobar"),
				desc = i(2),
				rhs = i(4),
				autosnippet = c(3, { i(1), t(', snippetType = "autosnippet"') }),
			},
			{ repeat_duplicates = true }
		)
	),
	-- t
	s({ trig = "t", desc = "A LuaSnip textNode", hidden = true }, { t('t("'), i(1), t('")') }),
}
