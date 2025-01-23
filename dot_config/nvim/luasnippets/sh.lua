-- P2: Migrate all useful Bash snippets.
local utils = require("util.snip_utils")

return {
	-- SNIPPET: if
	s(
		{ trig = "if", desc = "An if-logic branch." },
		fmt(
			[===[
      if [[ {cond} ]]; then
        {body}
      fi
    ]===],
			{
				cond = i(1),
				body = d(2, utils.get_visual("  ")),
			}
		)
	),
}
