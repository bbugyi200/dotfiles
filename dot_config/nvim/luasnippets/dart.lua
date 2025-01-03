local utils = require("snip_utils")

return {
	-- elif
	s(
		{ trig = "elif", desc = "Else-If logic branch", snippetType = "autosnippet", hidden = true },
		fmta(
			[[
  else if (<>) {
    <>
  }
  ]],
			{
				i(1),
				d(2, utils.get_visual),
			}
		)
	),
	-- if
	s(
		{ trig = "if", desc = "If logic branch", hidden = true },
		fmta(
			[[
  if (<>) {
    <>
  }
  ]],
			{
				i(1),
				d(2, utils.get_visual),
			}
		)
	),
	-- ife
	s(
		{ trig = "ife", desc = "If-else logic branch", snippetType = "autosnippet", hidden = true },
		fmta(
			[[
  if (<>) {
    <>
  } else {
    <>
  }
  ]],
			{
				i(1),
				i(2),
				d(3, utils.get_visual),
			}
		)
	),
}
