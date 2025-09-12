--- AI-powered coding, seamlessly in Neovim.

local bb = require("bb_utils")
local cc = require("plugins.codecompanion.common")

-- Create an adapter for Anthropic models.
--
-- @param model string The model to use for the adapter.
local function create_anthropic_adapter(model)
	return function()
		return require("codecompanion.adapters").extend("anthropic", {
			env = { api_key = "cmd:pass show claude_nvim_api_key" },
			schema = {
				model = {
					default = model,
				},
			},
		})
	end
end

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
					acp = {
						claude_code = function()
							return require("codecompanion.adapters").extend("claude_code", {
								env = {
									CLAUDE_CODE_OAUTH_TOKEN = "cmd:pass show claude_code_oauth_token",
								},
							})
						end,
					},
					http = {
						big_claude = create_anthropic_adapter("claude-sonnet-4-20250514"),
						little_claude = create_anthropic_adapter("claude-3-7-sonnet-20250219"),
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
				},
				extensions = {
					history = {
						opts = {
							title_generation_opts = {
								adapter = "little_claude",
							},
						},
					},
				},
				strategies = {
					chat = {
						adapter = "claude_code",
					},
					inline = {
						adapter = "big_claude",
					},
					cmd = {
						adapter = "big_claude",
					},
				},
			}),
			init = function()
				cc.common_init()

				-- KEYMAP: <leader>ccs
				cc.create_adapter_switch_keymap("claude_code", "big_claude")
			end,
		},
	})
end
