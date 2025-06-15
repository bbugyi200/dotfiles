--- AI-powered coding, seamlessly in Neovim.

local bb = require("bb_utils")
local cc = require("plugins.codecompanion.common")

if bb.is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use external LLM
	-- tools like OpenAI or Anthropic.
	return {}
else
	return vim.tbl_deep_extend("force", cc.common_plugin_config, {
		-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
		{
			opts = vim.tbl_deep_extend("force", cc.common_setup_opts, {
				adapters = {
					anthropic = function()
						return require("codecompanion.adapters").extend("anthropic", {
							env = { api_key = "cmd:pass show claude_nvim_api_key" },
							schema = {
								model = {
									default = "claude-sonnet-4-20250514",
								},
							},
						})
					end,
					openai = function()
						return require("codecompanion.adapters").extend("openai", {
							env = { api_key = "cmd:pass show chatgpt_nvim_api_key" },
							schema = {
								model = {
									default = "gpt-4.1",
								},
							},
						})
					end,
				},
				strategies = {
					chat = {
						adapter = "anthropic",
					},
					inline = {
						adapter = "anthropic",
					},
					cmd = {
						adapter = "anthropic",
					},
				},
			}),
			init = function()
				cc.common_init()

				-- KEYMAP: <leader>ccs
				cc.create_adapter_switch_keymap("anthropic", "openai")
			end,
		},
	})
end
