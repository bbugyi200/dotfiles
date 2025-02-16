-- P2: Migrate all useful Bash snippets.
--   [ ] Add '$' snippet.
--   [ ] Add '$$' snippet.
--   [ ] Add 'for' snippet.
--   [ ] Add 'f' snippet.
local utils = require("util.snip_utils")

-- Temp comment.
return {
	-- SNIPPET: $
	s({ trig = "$", desc = "Shortcut for quoted variable reference." }, { t('"${'), i(1), t('}"') }),
	-- SNIPPET: arg
	s({ trig = "arg", desc = "Store a command-line argument." }, {
		c(1, { sn(nil, { t("local "), i(1, "foobar") }), sn(nil, { t(""), i(1, "foobar") }) }),
		t({ '="$1"', "shift" }),
	}),
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
				if_body = i(2),
				else_body = d(3, utils.get_visual("  ")),
			}
		)
	),
}
