--- Enable code completion using Copilot.

-- Imports
local is_goog_machine = require("util.is_goog_machine").is_goog_machine
-- Variables
local copilot_plugin_name = "zbirenbaum/copilot.lua"

if is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use Copilot.
	return {}
else
	-- PLUGIN: http://github.com/zbirenbaum/copilot.lua
	return {
		{
			copilot_plugin_name,
			cmd = "Copilot",
			event = "InsertEnter",
			opts = {
				suggestion = { enabled = false },
				panel = { enabled = false },
				filetypes = {
					dart = true,
					lua = true,
					java = true,
					markdown = true,
					python = true,
					rust = true,
					shell = true,
				},
			},
		},
		{ "zbirenbaum/copilot-cmp", opts = {}, dependencies = { copilot_plugin_name } },
		{ "AndreM222/copilot-lualine", dependencies = { copilot_plugin_name } },
	}
end
