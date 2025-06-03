local cc = require("plugins.codecompanion.common")

return vim.tbl_deep_extend("force", cc.common_setup, {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		config = function()
			local goose = require("plugins.google.codecompanion.goose")
			goose.setup({
				auto_start_backend = false,
				auto_start_silent = false,
				model = "goose-v3.5-s",
				temperature = 0.1,
				max_decoder_steps = 8192,
				endpoint = "http://localhost:8649/predict",
				debug = vim.env.CC_GOOSE_DEBUG ~= nil,
				debug_backend = false,
			})

			require("codecompanion").setup({
				adapters = {
					goose = goose.get_adapter(),
				},
				display = {
					chat = {
						show_settings = true,
					},
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
					history = {
						enabled = true,
						opts = {
							-- Keymap to open history from chat buffer (default: gh)
							keymap = "gh",
							-- Keymap to save the current chat manually (when auto_save is disabled)
							save_chat_keymap = "sc",
							-- Save all chats by default (disable to save only manually using 'sc')
							auto_save = true,
							-- Number of days after which chats are automatically deleted (0 to disable)
							expiration_days = 0,
							-- Picker interface ("telescope" or "snacks" or "fzf-lua" or "default")
							picker = "telescope",
							-- Automatically generate titles for new chats
							auto_generate_title = true,
							---On exiting and entering neovim, loads the last chat on opening chat
							continue_last_chat = false,
							---When chat is cleared with `gx` delete the chat from history
							delete_on_clearing_chat = false,
							---Directory path to save the chats
							dir_to_save = vim.fn.stdpath("data") .. "/codecompanion-history",
							---Enable detailed logging for history extension
							enable_logging = false,
						},
					},
				},
				strategies = {
					chat = {
						adapter = "goose",
						keymaps = {
							completion = {
								modes = {
									i = "<c-d>",
								},
							},
							close = { modes = { n = "q", i = "<c-c>" } },
							regenerate = { modes = { n = "R" } },
							send = {
								modes = { n = "<C-s>", i = "<C-s>" },
							},
							stop = { modes = { n = "Q" } },
							watch = { modes = { n = "gW" } },
						},
						slash_commands = {
							buffer = {
								keymaps = {
									modes = {
										i = "<leader>b",
										n = "gb",
									},
								},
							},
							workspace = {
								keymaps = {
									modes = {
										i = "<leader>w",
										n = "gw",
									},
								},
							},
						},
					},
					inline = {
						adapter = "goose",
					},
					cmd = {
						adapter = "goose",
					},
				},
			})
		end,
		init = function()
			cc.common_init()

			-- AUTOCMD: Configure 'ge' keymap to comment-paste clipboard and transform code.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "codecompanion" },
				callback = function()
					-- KEYMAP: ge
					vim.keymap.set("n", "ge", function()
						-- Navigate to previous buffer
						vim.cmd("wincmd w")

						-- Jump to bottom of buffer
						vim.cmd("normal! G")

						-- Paste clipboard contents
						vim.cmd("normal! p")

						-- Comment out the pasted content
						vim.cmd("normal gcG")

						-- Run the transform command
						vim.cmd("TransformCode Implement the edits described at the bottom of the file in comments.")
					end, { desc = "Comment-paste clipboard and transform code", buffer = 0 })
				end,
			})
		end,
	},
})
