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
			opts = {
				adapters = {
					anthropc = function()
						return require("codecompanion.adapters").extend("anthropic", {
							env = { api_key = "cmd:pass show claude_nvim_api_key" },
							schema = {
								model = {
									default = "claude-3-7-sonnet-20250219",
								},
							},
						})
					end,
					openai = function()
						return require("codecompanion.adapters").extend("openai", {
							env = { api_key = "cmd:pass show chatgpt_nvim_api_key" },
							schema = {
								model = {
									default = "gpt-4.1-2025-04-14",
								},
							},
						})
					end,
				},
				strategies = {
					chat = {
						adapter = "anthropic",
						keymaps = {
							close = { modes = { n = "q", i = "<c-c>" } },
						},
					},
					inline = {
						adapter = "copilot",
					},
					cmd = {
						adapter = "anthropic",
					},
				},
			},
			init = function()
				-- KEYMAP: <leader>ccc
				vim.keymap.set("n", "<leader>ccc", ":CodeCompanionChat<CR>", { desc = "Open CodeCompanion Chat" })
			end,
		},
	}
end
