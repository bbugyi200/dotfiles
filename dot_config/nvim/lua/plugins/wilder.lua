--- A more adventurous wildmenu.

return {
	-- PLUGIN: http://github.com/gelguy/wilder.nvim
	{
		"gelguy/wilder.nvim",
		opts = {
			modes = { ":", "/", "?" },
		},
		init = function()
			local wilder = require("wilder")
			local highlighters = {
				wilder.pcre2_highlighter(),
				wilder.lua_fzy_highlighter(),
			}

			local popupmenu_renderer = wilder.popupmenu_renderer(wilder.popupmenu_border_theme({
				border = "rounded",
				empty_message = wilder.popupmenu_empty_message_with_spinner(),
				highlighter = highlighters,
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
