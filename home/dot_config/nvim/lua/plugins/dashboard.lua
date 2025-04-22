--- Fancy and Blazing Fast start screen plugin of neovim.

local is_goog_machine = require("util.is_goog_machine")

--- Generates a list of dashboard shortcuts.
---
--- @return table<table> # A list of dashboard shortcut configurations.
local function get_shortcuts()
	local shortcuts = {}

	-- Only add CodeSearch shortcut if on a Google machine
	if is_goog_machine() then
		table.insert(shortcuts, {
			desc = "🔭 CodeSearch",
			group = "Special",
			action = "Telescope codesearch find_query",
			key = "c",
		})
	end

	-- Add the rest of the shortcuts
	table.insert(shortcuts, {
		desc = " dotfiles",
		group = "Number",
		action = "Telescope chezmoi find_files",
		key = "d",
	})

	if not is_goog_machine() then
		table.insert(shortcuts, {
			icon = " ",
			icon_hl = "@variable",
			desc = "Files",
			group = "Label",
			action = "Telescope find_files",
			key = "f",
		})
	end

	table.insert(shortcuts, {
		desc = " Sessions",
		group = "@function",
		action = "Autosession search",
		key = "s",
	})

	table.insert(shortcuts, {
		desc = "󰊳 Update",
		group = "@property",
		action = "Lazy update",
		key = "u",
	})

	table.insert(shortcuts, {
		desc = "❌ Quit",
		group = "ErrorMsg",
		action = "quit",
		key = "q",
	})

	return shortcuts
end

return {
	-- PLUGIN: http://github.com/nvimdev/dashboard-nvim
	{
		"nvimdev/dashboard-nvim",
		event = "VimEnter",
		dependencies = { "nvim-tree/nvim-web-devicons" },
		config = function()
			require("dashboard").setup({
				theme = "hyper",
				config = {
					week_header = {
						enable = true,
					},
					shortcut = get_shortcuts(),
				},
			})
		end,
	},
}
