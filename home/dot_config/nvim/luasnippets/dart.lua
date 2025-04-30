-- P2: Finish migrating all useful Dart snippets.
local utils = require("bb_utils.snip_utils")

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
				body = d(2, utils.get_visual("  ")),
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
				body = d(2, utils.get_visual("  ")),
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
				else_body = d(3, utils.get_visual("  ")),
			}
		)
	),
}
