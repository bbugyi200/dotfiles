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
	-- SNIPPET: scuba
	s(
		{ trig = "scuba", desc = "Create a scuba diff test." },
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
}
