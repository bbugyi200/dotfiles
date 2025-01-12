local is_goog_machine = require("util.is_goog_machine").is_goog_machine

if is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use Copilot.
	return {}
else
	return {
		{
			"zbirenbaum/copilot.lua",
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
		{ "zbirenbaum/copilot-cmp", opts = {} },
		{ "AndreM222/copilot-lualine" },
	}
end
