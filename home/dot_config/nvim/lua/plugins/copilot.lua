--- Enable code completion using Copilot.

local bb = require("bb_utils")

if bb.is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use Copilot.
	return {}
else
	local copilot_plugin_name = "zbirenbaum/copilot.lua"
	return {
		-- PLUGIN: http://github.com/zbirenbaum/copilot.lua
		{
			copilot_plugin_name,
			cmd = "Copilot",
			event = "InsertEnter",
			opts = {
				suggestion = { enabled = true },
				panel = { enabled = true },
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
		-- PLUGIN: http://github.com/zbirenbaum/copilot-cmp
		{ "zbirenbaum/copilot-cmp", opts = {}, dependencies = { copilot_plugin_name } },
		-- PLUGIN: http://github.com/AndreM222/copilot-lualine
		{ "AndreM222/copilot-lualine", dependencies = { copilot_plugin_name } },
	}
end
