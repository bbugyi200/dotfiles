--- ChatGPT Neovim Plugin: Effortless Natural Language Generation with OpenAI's ChatGPT API

local is_goog_machine = require("util.is_goog_machine").is_goog_machine

if is_goog_machine() then
	return {}
else
	return {
		-- PLUGIN: http://github.com/jackMort/ChatGPT.nvim
		{
			"jackMort/ChatGPT.nvim",
			event = "VeryLazy",
			opts = { api_key_cmd = "pass show chatgpt_nvim_api_key" },
			dependencies = {
				"MunifTanjim/nui.nvim",
				"nvim-lua/plenary.nvim",
				"folke/trouble.nvim", -- optional
				"nvim-telescope/telescope.nvim",
			},
		},
	}
end
