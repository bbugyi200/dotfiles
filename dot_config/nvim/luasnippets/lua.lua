return {
	-- i
	s({ trig = "i", desc = "A LuaSnip insertNode", hidden = true }, { t("i("), i(1, "1"), t(', "'), i(2), t('")') }),
	-- l
	s({ trig = "l", desc = "Shortcut for <leader>" }, { t("<leader>") }),
	-- ll
	s({ trig = "ll", desc = "Shortcut for <localleader>" }, { t("<localleader>") }),
	-- m
	s(
		{ trig = "m", desc = "Add a NeoVim keymap." },
		{ t('vim.keymap.set("'), i(1, "n"), t('", "'), i(2), t('", "'), i(3), t('", { desc = "'), i(4), t('" })') }
	),
	-- s
	s(
		{ trig = "s", desc = "A LuaSnip snippet", hidden = true },
		fmta(
			[[
  -- <name>
  s(
    { <opts><autosnip> },
    { <rhs> }
  ),
  ]],
			{
				name = i(1, "foobar", { key = "name" }),
				opts = c(2, {
					sn(nil, { t('trig = "'), rep(k("name")), t('", desc = "'), i(1), t('"') }),
					sn(nil, {
						t('trig = "'),
						i(1),
						t('", name = "'),
						rep(k("name")),
						t('", regTrig = true, desc = "'),
						i(2),
						t('", hidden = true'),
					}),
				}),
				autosnip = c(3, { t(', snippetType = "autosnippet"'), t("") }),
				rhs = i(4),
			}
		),
		{ repeat_duplicates = true }
	),
	-- t
	s({ trig = "t", desc = "A LuaSnip textNode", hidden = true }, { t('t("'), i(1), t('")') }),
}
