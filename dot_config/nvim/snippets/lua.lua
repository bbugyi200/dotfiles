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
    { trig = "<trig>", desc = "<desc>" },
    { <rhs> }
  ),
  ]],
			{
				trig = i(1),
				desc = i(2),
				rhs = i(3),
			},
			{ repeat_duplicates = true }
		)
	),
	-- t
	s({ trig = "t", desc = "A LuaSnip textNode", hidden = true }, { t('t("'), i(1), t('")') }),
}
