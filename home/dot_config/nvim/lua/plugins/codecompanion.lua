--- AI-powered coding, seamlessly in Neovim.

local bb = require("bb_utils")

if bb.is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use external LLM
	-- tools like OpenAI or Anthropic.
	return {}
else
	return {
		-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
		{
			"olimorris/codecompanion.nvim",
			version = "*",
			dependencies = {
				{ "nvim-lua/plenary.nvim", branch = "master" },
				"nvim-treesitter/nvim-treesitter",
			},
			opts = {},
		},
	}
end
