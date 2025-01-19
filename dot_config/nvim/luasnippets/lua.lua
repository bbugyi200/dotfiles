-- P1: Add snippet for require() imports!
-- P2: Add snippet for autocmds with AUTOCMD comment prefix!
-- P3: Add choice to 's' snippet for fmt()!
local utils = require("util.snip_utils")

return {
	-- SNIPPET: \c
	s({ trig = "\\c", desc = "Shortcut for <cr>", wordTrig = false, snippetType = "autosnippet" }, { t("<cr>") }),
	-- SNIPPET: \e
	s({ trig = "\\e", desc = "Shortcut for <esc>", wordTrig = false, snippetType = "autosnippet" }, { t("<esc>") }),
	-- SNIPPET: \m
	s({ trig = "\\m", desc = "Shortcut for <cmd>", wordTrig = false, snippetType = "autosnippet" }, { t("<cmd>") }),
	-- SNIPPET: do
	s(
		{ trig = "do", desc = "A do-block." },
		fmt(
			[[
      do
        {}
      end
    ]],
			{ d(1, utils.get_visual("  ")) }
		)
	),
	-- SNIPPET: f
	s(
		{ trig = "f", desc = "An inline function()." },
		{ t("function("), i(1), t(") "), d(2, utils.get_visual()), t(" end") }
	),
	-- SNIPPET: fu
	s(
		{ trig = "fu", desc = "A local / module-level function()." },
		fmt(
			[[
    --- {doc}
    {func_type}{name}({params})
      {body}
    end
  ]],
			{
				func_type = c(1, {
					sn(nil, { i(1), t("local function ") }),
					sn(nil, { i(1), t("function M.") }),
				}),
				name = i(2, "f", { key = "name" }),
				params = i(3, "", { key = "params" }),
				doc = d(4, function(args)
					local params = args[1][1] or ""
					local node_table = { i(1) }
					if params ~= "" then
						table.insert(node_table, t({ "", "---" }))
					end
					local idx = 2
					for word in string.gmatch(params, "([^, ]+)") do
						table.insert(node_table, t({ "", "---@param " }))
						table.insert(node_table, t(word .. " "))
						table.insert(node_table, i(idx))
						idx = idx + 1
					end
					return sn(nil, node_table)
				end, { 3 }),
				body = d(
					5,
					utils.get_visual(
						"  ",
						sn(nil, {
							t('print("Calling '),
							rep(k("name")),
							t('()..."'),
							m(k("params"), "^.", ', "[args =", ', ""),
							rep(k("params")),
							m(k("params"), "^.", ' .. "]"', ""),
							t(")"),
							i(1),
						})
					)
				),
			}
		)
	),
	-- SNIPPET: i
	s(
		{ trig = "i", desc = "A LuaSnip insertNode", hidden = true },
		{ t("i("), i(1, "1"), c(2, { sn(nil, { t("),"), i(1) }), sn(nil, { t(', "'), i(1), t('"),') }) }) }
	),
	-- SNIPPET: if
	s(
		{ trig = "if", desc = "An if-logic branch." },
		fmt(
			[[
      if {} then
        {}
      end
    ]],
			{
				i(1),
				d(2, utils.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: k
	s(
		{ trig = "k", desc = "Add a NeoVim keymap." },
		fmta(
			[[
  -- KEYMAP(<mode>): <lhs>
  vim.keymap.set("<mode>", "<lhs>", "<rhs>", { desc = "<desc>" })
]],
			{
				mode = i(1, "n"),
				lhs = i(2, "", { key = "lhs" }),
				rhs = i(3),
				desc = i(4),
			},
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: l
	s({ trig = "l", desc = "Shortcut for <leader>" }, { t("<leader>") }),
	-- SNIPPET: ll
	s({ trig = "ll", desc = "Shortcut for <localleader>" }, { t("<localleader>") }),
	-- SNIPPET: s
	s(
		{ trig = "s", desc = "A LuaSnip snippet", hidden = true },
		fmta(
			[[
  -- SNIPPET: <name>
  s(
    { <opts><autosnip> },
    { <rhs> }
  ),
  ]],
			{
				name = i(1, "foobar", { key = "name" }),
				opts = c(2, {
					sn(nil, { t('trig = "'), rep(k("name")), t('", desc = "'), i(1), t('"') }),
					sn(nil, {
						t('trig = "'),
						i(1),
						t('", name = "'),
						rep(k("name")),
						t('", regTrig = true, desc = "'),
						i(2),
						t('", hidden = true'),
					}),
				}),
				autosnip = c(3, { t(', snippetType = "autosnippet"'), t("") }),
				rhs = i(4),
			}
		),
		{ repeat_duplicates = true }
	),
	-- SNIPPET: t
	s({ trig = "t", desc = "A LuaSnip textNode", hidden = true }, { t('t("'), i(1), t('"),') }),
}
