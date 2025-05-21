-- P2: Finish migrating all useful Dart snippets.
local bb = require("bb_utils")

return {
	-- SNIPPET: elif
	s(
		{ trig = "elif", desc = "Else-If logic branch", snippetType = "autosnippet", hidden = true },
		fmta(
			[[
  else if (<cond>) {
    <body>
  }
  ]],
			{
				cond = i(1),
				body = d(2, bb.snip.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: f
	s(
		{ trig = "f", desc = "Short function..." },
		{ i(1, "Foobar"), t(" "), i(2, "getFoobar"), t("("), i(3), t(")"), t(" => "), i(4), t(";") }
	),
	-- SNIPPET: fu
	s(
		{ trig = "fu", desc = "Long function..." },
		fmta(
			[[
  <ret> <name>(<params>) {
    <body>
  }
  ]],
			{
				ret = i(1, "Foobar"),
				name = i(2),
				params = i(3),
				body = d(4, bb.snip.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: g
	s({ trig = "g", desc = "Getter" }, { i(1, "Foobar"), t(" get "), i(2, "foobar"), t(" => "), i(3), t(";") }),
	-- SNIPPET: grp
	s(
		{ trig = "grp", desc = "Create new Dart test group()..." },
		fmta(
			[[
  group('<desc>', () {
    <body>
  });
  ]],
			{
				desc = i(1),
				body = d(2, bb.snip.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: if
	s(
		{ trig = "if", desc = "If logic branch", hidden = true },
		fmta(
			[[
  if (<cond>) {
    <body>
  }
  ]],
			{
				cond = i(1),
				body = d(2, bb.snip.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: ife
	s(
		{ trig = "ife", desc = "If-else logic branch", snippetType = "autosnippet", hidden = true },
		fmta(
			[[
        if (<cond>) {
          <if_body>
        } else {
          <else_body>
        }
        ]],
			{
				cond = i(1),
				if_body = i(2),
				else_body = d(3, bb.snip.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: in
	s({ trig = "in", desc = "@Input()" }, { t({ "@Input()", "" }) }),
	-- SNIPPET: ov
	s({ trig = "ov", desc = "@override" }, { t({ "@override", "" }) }),
	-- SNIPPET: scu
	s(
		{ trig = "scu", desc = "Create a scuba diff test." },
		fmta(
			[[
        await scuba.diffScreenshot('<name>');
        await <testBed>.checkAccessibility();
        ]],
			{
				name = i(1),
				testBed = i(2, "testBed"),
			}
		)
	),
	-- SNIPPET: td
	s({ trig = "td", desc = "// TODO(bbugyi): some todo comment..." }, { t("// TODO(bbugyi): ") }),
	-- SNIPPET: tst
	s(
		{ trig = "tst", desc = "Create new Dart test()..." },
		fmta(
			[[
  test('<desc>', () {
    <body>
  });
  ]],
			{
				desc = i(1),
				body = d(2, bb.snip.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: xp
	s(
		{ trig = "xp", desc = "expect(actual, matcher)" },
		{ t("expect("), i(1, "actual"), t(", "), i(2, "matcher"), t(");") }
	),
}
