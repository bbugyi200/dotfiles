return {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		"olimorris/codecompanion.nvim",
		version = "*",
		dependencies = {
			{ "nvim-lua/plenary.nvim", branch = "master" },
			"nvim-treesitter/nvim-treesitter",
			-- For fidget.nvim Integration...
			"j-hui/fidget.nvim",
			-- Extensions
			"ravitemer/codecompanion-history.nvim",
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
		config = function()
			local goose = require("plugins.google.codecompanion.goose")
			goose.setup({
				auto_start_backend = false,
				auto_start_silent = false,
				model = "goose-v3.5-m",
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
								index = 1,
								callback = "keymaps.completion",
								description = "Completion Menu",
							},
							close = { modes = { n = "q", i = "<c-c>" } },
							send = {
								modes = { n = "<C-s>", i = "<C-s>" },
							},
							stop = { modes = { n = "Q" } },
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
			require("extra.codecompanion.fidget").init()
			require("extra.codecompanion.extmarks").setup()

			-- AUTOCMD: Automatically format buffer with conform.nvim after inline request completes.
			vim.api.nvim_create_autocmd({ "User" }, {
				pattern = "CodeCompanionInline*",
				group = vim.api.nvim_create_augroup("CodeCompanionHooks", {}),
				callback = function(request)
					if request.match == "CodeCompanionInlineFinished" then
						-- Format the buffer after the inline request has completed
						require("conform").format({ bufnr = request.data.bufnr })
					end
				end,
			})

			-- AUTOCMD: Configure keymaps for CodeCompanion chat buffer.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "codecompanion" },
				callback = function()
					-- KEYMAP: <cr>
					vim.keymap.set("n", "<cr>", function()
						-- Yank the query to my clipboard.
						vim.cmd("normal! yG")
						-- Simulate keypress to tirgger keymap that submits query!
						vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<c-s>", true, true, true), "v", true)
					end, { buffer = true, desc = "Submit CodeCompanion query." })

					-- KEYMAP: <c-q>
					vim.keymap.set("i", "<c-q>", function()
						-- Exit insert mode
						vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, true, true), "n", false)
						-- Yank the query to my clipboard.
						vim.cmd("normal! yG")
						-- Simulate keypress to tirgger keymap that submits query!
						vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<c-s>", true, true, true), "v", true)
					end, { buffer = true, desc = "Submit CodeCompanion query from insert mode." })
				end,
			})

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: <leader>C
			vim.keymap.set("n", "<leader>C", "<cmd>CodeCompanionChat Toggle<cr>", {
				desc = "CodeCompanionChat Toggle",
			})

			-- KEYMAP GROUP: <leader>cc
			vim.keymap.set("n", "<leader>cc", "<nop>", { desc = "codecompanion.nvim" })
			-- KEYMAP: <leader>cca
			vim.keymap.set("n", "<leader>cca", "<cmd>CodeCompanionActions<cr>", { desc = "CodeCompanionActions" })
			-- KEYMAP: <leader>ccc
			vim.keymap.set("n", "<leader>ccc", "<cmd>CodeCompanionChat<cr>", {
				desc = "CodeCompanionChat",
			})
			-- KEYMAP: <leader>cci
			vim.keymap.set({ "n", "v" }, "<leader>cci", ":CodeCompanion ", { desc = ":CodeCompanion <QUERY>" })
		end,
	},
}
