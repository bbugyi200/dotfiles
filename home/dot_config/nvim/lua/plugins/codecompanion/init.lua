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
				vim.keymap.set("n", "<leader>ccs", function()
					local config = require("codecompanion.config")
					local current = config.strategies.chat.adapter
					local new = current == "anthropic" and "openai" or "anthropic"

					for _, strategy in pairs(config.strategies) do
						strategy.adapter = new
					end

					vim.notify("Switched CodeCompanion adapter to " .. new, vim.log.levels.INFO)
				end, { desc = "Switch AI Adapter" })
			end,
		},
	})
end
