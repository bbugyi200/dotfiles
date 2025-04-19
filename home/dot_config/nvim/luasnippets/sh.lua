local utils = require("util.snip_utils")

return {
	-- SNIPPET: $
	s({ trig = "$", desc = "Shortcut for quoted variable reference." }, { t('"${'), i(1), t('}"') }),
	-- SNIPPET: arg
	s({ trig = "arg", desc = "Store a command-line argument in a variable." }, {
		i(1, "foobar"),
		t({ '="$1"', "shift" }),
	}),
	-- SNIPPET: f
	s(
		{ trig = "f", desc = "A shell function (ex: function foobar())." },
		fmta(
			[[
    # <doc>
    function <name>() {
      <body>
    }
  ]],
			{
				name = i(1, "foobar"),
				doc = i(2),
				body = d(3, utils.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: for
	s({ trig = "for", desc = "A for-loop that iterates over an expression." }, {
		t("for "),
		i(1, "item"),
		t(" in "),
		t("$("),
		i(2),
		t({ "); do", "  " }),
		d(3, utils.get_visual("  ")),
		t({ "", "done" }),
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
	-- SNIPPET: ifr
	s(
		{ trig = "ifr", desc = "Call the run() function if this script was not sourced." },
		fmta(
			[===[
      if [[ "${SCRIPTNAME}" == "$(basename "${BASH_SOURCE[0]}")" ]]; then
        run "$@"
      fi
    ]===],
			{}
		)
	),
	-- SNIPPET: larg
	s({ trig = "larg", desc = "Store a function argument in a variable." }, {
		t("local "),
		i(1, "foobar"),
		t({ '="$1"', "shift" }),
	}),
	-- SNIPPET: scd
	s(
		{ trig = "scd", desc = "Pragma to disable shellcheck error on the next line." },
		{ t("# shellcheck disable=SC"), i(1) }
	),
}
