--- A more adventurous wildmenu.

return {
	-- PLUGIN: http://github.com/gelguy/wilder.nvim
	{
		"gelguy/wilder.nvim",
		build = ":UpdateRemotePlugins",
		dependencies = { "romgrk/fzy-lua-native" },
		opts = {
			modes = { ":", "/", "?" },
		},
		init = function()
			local wilder = require("wilder")
			local highlighters = {
				wilder.lua_fzy_highlighter(),
			}

			local popupmenu_renderer = wilder.popupmenu_renderer(wilder.popupmenu_border_theme({
				border = "rounded",
				pumblend = 20,
				empty_message = wilder.popupmenu_empty_message_with_spinner(),
				highlighter = highlighters,
				highlights = {
					accent = wilder.make_hl(
						"WilderAccent",
						"Pmenu",
						{ { a = 1 }, { a = 1 }, { foreground = "#f4468f" } }
					),
				},
				left = {
					" ",
					wilder.popupmenu_devicons(),
					wilder.popupmenu_buffer_flags({
						flags = " a + ",
						icons = { ["+"] = "", a = "", h = "" },
					}),
				},
				right = {
					" ",
					wilder.popupmenu_scrollbar(),
				},
			}))
			wilder.set_option("renderer", popupmenu_renderer)
		end,
	},
}
