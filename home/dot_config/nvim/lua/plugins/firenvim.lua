--- Embed Neovim in Chrome, Firefox & others.

return {
	-- PLUGIN: http://github.com/glacambre/firenvim
	{
		"glacambre/firenvim",
		build = ":call firenvim#install(0)",
		init = function()
			vim.g.firenvim_config = {
				globalSettings = { alt = "all" },
				localSettings = {
					[".*"] = {
						cmdline = "neovim",
						content = "text",
						priority = 0,
						selector = "textarea",
						takeover = "once",
					},
				},
			}
		end,
	},
}
