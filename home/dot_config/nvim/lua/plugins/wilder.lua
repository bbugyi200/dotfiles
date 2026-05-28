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
			local devicon_expansions = {
				buffer = true,
				dir = true,
				file = true,
				file_in_path = true,
				shellcmd = true,
			}
			local buffer_flag_expansions = {
				buffer = true,
				file = true,
				file_in_path = true,
			}
			local function component_for_expansions(component, expansions)
				return function(ctx, result)
					local data = result and result.data
					local expand = type(data) == "table" and data["cmdline.expand"] or nil
					if type(expand) ~= "string" or not expansions[expand] then
						return ""
					end

					local ok, value = pcall(component, ctx, result)
					if not ok then
						return ""
					end

					return value
				end
			end

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
					component_for_expansions(wilder.popupmenu_devicons(), devicon_expansions),
					component_for_expansions(
						wilder.popupmenu_buffer_flags({
							flags = " a + ",
							icons = { ["+"] = "", a = "", h = "" },
						}),
						buffer_flag_expansions
					),
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
