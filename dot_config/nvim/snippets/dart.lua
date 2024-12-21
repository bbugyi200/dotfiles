local function get_visual_text(_, snip)
	return snip.env.TM_SELECTED_TEXT or {}
end

return {
	s(
		{trig = "elif", desc = "Else-If logic branch", hidden = true},
		fmta(
			[[
  else if (<>) {
    <>
  }
  ]],
			{
				i(1),
				f(get_visual_text),
			}
		)
	),
	s(
		{trig = "if", desc = "If logic branch", hidden = true},
		fmta(
			[[
  if (<>) {
    <>
  }
  ]],
			{
				i(1),
				f(get_visual_text),
			}
		)
	),
	s(
		{trig = "ife", desc = "If-else logic branch", hidden = true},
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
				f(get_visual_text),
			}
		)
	),
}
