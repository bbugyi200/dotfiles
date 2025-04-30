-- P1: Add choice node to 'pl' and 'pll' snippets!
--   [ ] Share logic between 'pl' and 'pll' snippets! Use dynamic nodes with NO
--       annonymaous functions?!
-- P2: Add snippet for autocmds with AUTOCMD comment prefix!
-- P3: Add choice to 's' snippet for fmt()!
-- P3: Share logic between 'pl' and 'pll' snippets!

local utils = require("bb_utils.snip_utils")

return {
	-- SNIPPET: \c
	s({
		trig = "\\c",
		desc = "Shortcut for <cr>",
		wordTrig = false,
		snippetType = "autosnippet",
	}, { t("<cr>") }),
	-- SNIPPET: \e
	s({
		trig = "\\e",
		desc = "Shortcut for <esc>",
		wordTrig = false,
		snippetType = "autosnippet",
	}, { t("<esc>") }),
	-- SNIPPET: \m
	s({
		trig = "\\m",
		desc = "Shortcut for <cmd>",
		wordTrig = false,
		snippetType = "autosnippet",
	}, { t("<cmd>"), i(1), t("<cr>") }),
	-- SNIPPET: cmd
	s({
		trig = "cmd",
		desc = "Shortcut for vim.cmd([[...]])",
	}, { t({ "vim.cmd([[", "  " }), d(1, utils.get_visual("  ")), t({ "", "]])" }) }),
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
		{ t("function("), i(1), t({ ")", "  " }), d(2, utils.get_visual("  ")), t({ "", "end" }) }
	),
	-- SNIPPET: for
	s(
		{ trig = "for", desc = "A for-loop." },
		fmt(
			[[
      for {cond} in {iter} do
        {body}
      end
    ]],
			{
				cond = i(1, "item"),
				iter = i(2, "iter"),
				body = d(3, utils.get_visual("  ")),
			}
		)
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
	s({
		trig = "i",
		desc = "A LuaSnip insertNode",
		hidden = true,
	}, {
		t("i("),
		i(1, "1"),
		c(2, { sn(nil, { t("),"), i(1) }), sn(nil, { t(', "'), i(1), t('"),') }) }),
	}),
	-- SNIPPET: if
	s(
		{ trig = "if", desc = "An 'if' logic branch." },
		fmt(
			[[
      if {cond} then
        {body}
      end
    ]],
			{
				cond = i(1),
				body = d(2, utils.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: ife
	s(
		{ trig = "ife", desc = "An 'if-else' logic branch." },
		fmt(
			[[
      if {cond} then
        {if_body}
      else
        {else_body}
      end
    ]],
			{
				cond = i(1),
				if_body = i(2),
				else_body = d(3, utils.get_visual("  ")),
			}
		)
	),
	-- SNIPPET: k
	s(
		{ trig = "k", desc = "Add a Neovim keymap." },
		fmta(
			[[
      -- KEYMAP: <lhs>
      vim.keymap.set(<mode>, "<lhs>", "<rhs>", { desc = "<desc>" })
    ]],
			{
				mode = c(1, {
					sn(nil, { t('"n'), i(1), t('"') }),
					sn(nil, { t('{ "n"'), i(1), t(" }") }),
				}),
				lhs = i(2),
				rhs = i(3),
				desc = i(4),
			},
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: kg
	s(
		{ trig = "kg", desc = "Add a Neovim keymap group." },
		fmta(
			[[
      -- KEYMAP GROUP: <lhs>
      vim.keymap.set(<mode>, "<lhs>", "<<nop>>", { desc = "<desc>" })
    ]],
			{
				mode = c(1, {
					sn(nil, { t('"n'), i(1), t('"') }),
					sn(nil, { t('{ "n"'), i(1), t(" }") }),
				}),
				lhs = i(2),
				desc = i(3),
			},
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: l
	s({ trig = "l", desc = "Shortcut for <leader>" }, { t("<leader>") }),
	-- SNIPPET: ll
	s({ trig = "ll", desc = "Shortcut for <localleader>" }, { t("<localleader>") }),
	-- SNIPPET: pl
	s(
		{ trig = "pl", desc = "A Neovim plugin in an EXISTING file." },
		fmta(
			[[
      -- PLUGIN: http://github.com/<plugin>
      {
        "<plugin>",
        opts = {<opts>}
      },
    ]],
			{ plugin = i(1), opts = i(2) },
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: pll
	s(
		{ trig = "pll", desc = "A Neovim plugin in a NEW file." },
		fmta(
			[[
      --- <doc>

      return {
        -- PLUGIN: http://github.com/<plugin>
        {
          "<plugin>",
          opts = {<opts>}
        },
      }
    ]],
			{ plugin = i(1), doc = i(2), opts = i(3) },
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: pls
	s(
		{ trig = "pls", desc = "A simple (no opts) Neovim plugin in an EXISTING file." },
		fmta(
			[[
      -- PLUGIN: http://github.com/<plugin>
      "<plugin>",
    ]],
			{ plugin = i(1) },
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: r
	s({
		trig = "r",
		desc = "Shortcut for an anonymous import via require()",
	}, {
		t('require("'),
		i(1),
		t('")'),
	}),
	-- SNIPPET: rr
	s({ trig = "rr", desc = "Shortcut for importing modules with require()" }, {
		t("local "),
		i(1, "foobar", { key = "varname" }),
		t(' = require("'),
		i(2),
		rep(k("varname")),
		i(3),
		t('")'),
	}),
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
				autosnip = c(3, { t(""), t(', snippetType = "autosnippet"') }),
				rhs = i(4),
			}
		),
		{ repeat_duplicates = true }
	),
	-- SNIPPET: t
	s({ trig = "t", desc = "A LuaSnip textNode", hidden = true }, { t('t("'), i(1), t('"),') }),
	-- SNIPPET: vn
	s({ trig = "vn", desc = "Shortcut for vim.notify()." }, {
		t('vim.notify("'),
		i(1),
		t('"'),
		c(2, {
			sn(nil, { t(")"), i(1) }),
			sn(nil, { t(", vim.log.levels."), i(1, "ERROR"), t(")") }),
			sn(nil, { t(", vim.log.levels."), i(1, "ERROR"), t(', { title = "'), i(2), t('"})') }),
		}),
	}),
}
