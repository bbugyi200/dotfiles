local utils = require("snip_utils")

return {
	-- sn
	s(
		{ trig = "sn", desc = "A LuaSnip snippet", hidden = true },
		fmta(
			[[
  -- <trig>
  s(
    { trig = "<trig>", desc = "<desc>" },
    { <rhs> },
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
}
