-- P0: Add 'pl' and 'pll' snippets that include '--- PLUGIN:' comment.
--   [ ] Use 'pl' to add a plugin to an existing file (ex: misc.lua or telescope.lua)!
--   [ ] Use 'pll' when creating a new plugin/*.lua file!
--   [ ] Include URL to GitHub in PLUGIN comment?
-- P1: Add 'for' snippet for Lua for-loops!
-- P1: Add snippet for require() imports!
-- P2: Add snippet for autocmds with AUTOCMD comment prefix!
-- P3: Add choice to 's' snippet for fmt()!
-- P3: Share logic between 'pl' and 'pll' snippets!
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
  -- KEYMAP(<upper_mode>): <lhs>
  vim.keymap.set("<mode>", "<lhs>", "<rhs>", { desc = "<desc>" })
]],
			{
				upper_mode = i(1, "N"),
				mode = d(2, function(args)
					local mode = args[1][1] or ""
					return sn(nil, { t(mode:lower()) })
				end, { 1 }),
				lhs = i(3, "", { key = "lhs" }),
				rhs = i(4),
				desc = i(5),
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
		{ trig = "pl", desc = "A single NeoVim plugin." },
		fmta(
			[[
      -- PLUGIN: http://github.com/<plugin>
      { "<plugin>", enabled = true },
      {
        "<plugin>",
        enabled = false,
        opts = {<opts>},
      },
    ]],
			{ plugin = i(1), opts = i(2) },
			{ repeat_duplicates = true }
		)
	),
	-- SNIPPET: pll
	s(
		{ trig = "pll", desc = "A single NeoVim plugin." },
		fmta(
			[[
      --- <doc>

      return {
        -- PLUGIN: http://github.com/<plugin>
        { "<plugin>", enabled = true },
        {
          "<plugin>",
          enabled = false,
          opts = {<opts>},
        },
      }
    ]],
			{ doc = i(1), plugin = i(2), opts = i(3) },
			{ repeat_duplicates = true }
		)
	),
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
