local is_goog_machine = require("util.is_goog_machine").is_goog_machine

if is_goog_machine() then
	-- When working from a Google machine, we use vvvv/ai.nvim instead of CoPilot.
	return {}
else
	return {
		{
			"zbirenbaum/copilot.lua",
			opts = {},
		},
	}
end
