-- P2: Migrate all useful Bash snippets.
--   [ ] Add '$' snippet.
--   [ ] Add '$$' snippet.
--   [ ] Add 'for' snippet.
--   [ ] Add 'f' snippet.
local utils = require("util.snip_utils")

return {
	-- SNIPPET: if
	s(
		{ trig = "if", desc = "An 'if' logic branch." },
		fmt(
			[===[
      if {cond}; then
        {body}
      fi
    ]===],
			{
				cond = c(1, { sn(nil, { t("[[ "), i(1), t(" ]]") }), sn(nil, { i(1) }) }),
				body = d(2, utils.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: ife
	s(
		{ trig = "ife", desc = "An 'if-else' logic branch." },
		fmt(
			[===[
      if {cond}; then
        {if_body}
      else
        {else_body}
      fi
    ]===],
			{
				cond = c(1, { sn(nil, { t("[[ "), i(1), t(" ]]") }), sn(nil, { i(1) }) }),
				else_body = d(2, utils.get_visual("  ")),
				if_body = i(3),
			}
		)
	),
}
