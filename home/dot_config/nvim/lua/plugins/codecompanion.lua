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
				"j-hui/fidget.nvim",
				{
					-- PLUGIN: http://github.com/ravitemer/mcphub.nvim
					{
						"ravitemer/mcphub.nvim",
						dependencies = {
							"nvim-lua/plenary.nvim", -- Required for Job and HTTP requests
						},
						build = "npm install -g mcp-hub@latest",
						opts = {},
					},
				},
			},
			opts = {
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
				extensions = {
					mcphub = {
						callback = "mcphub.extensions.codecompanion",
						opts = {
							show_result_in_chat = true, -- Show the mcp tool result in the chat buffer
							make_vars = true, -- make chat #variables from MCP server resources
							make_slash_commands = true, -- make /slash_commands from MCP server prompts
						},
					},
				},
				strategies = {
					chat = {
						adapter = "anthropic",
						keymaps = {
							close = { modes = { n = "q", i = "<c-c>" } },
							stop = { modes = { n = "Q" } },
						},
					},
					inline = {
						adapter = "anthropic",
					},
					cmd = {
						adapter = "anthropic",
					},
				},
			},
			init = function()
				require("extra.codecompanion.fidget").init()
				require("extra.codecompanion.extmarks").setup()

				-- AUTOCMD: Format buffer after inline request.
				vim.api.nvim_create_autocmd({ "User" }, {
					pattern = "CodeCompanionInline*",
					group = vim.api.nvim_create_augroup("CodeCompanionHooks", {}),
					callback = function(request)
						if request.match == "CodeCompanionInlineFinished" then
							-- Format the buffer after the inline request has completed
							require("conform").format({ bufnr = request.buf })
						end
					end,
				})

				-- ╭─────────────────────────────────────────────────────────╮
				-- │                         KEYMAPS                         │
				-- ╰─────────────────────────────────────────────────────────╯
				-- KEYMAP GROUP: <leader>cc
				vim.keymap.set("n", "<leader>cc", "<nop>", { desc = "codecompanion.nvim" })
				-- KEYMAP: <leader>cca
				vim.keymap.set("n", "<leader>cca", "<cmd>CodeCompanionActions<cr>", { desc = "CodeCompanionActions" })
				-- KEYMAP: <leader>ccc
				vim.keymap.set(
					"n",
					"<leader>ccc",
					"<cmd>CodeCompanionChat Toggle<cr>",
					{ desc = "CodeCompanionChat Toggle" }
				)
				-- KEYMAP: <leader>cci
				vim.keymap.set(
					{ "n", "v" },
					"<leader>cci",
					":CodeCompanion #buffer ",
					{ desc = ":CodeCompanion #buffer <QUERY>" }
				)
			end,
		},
	}
end
