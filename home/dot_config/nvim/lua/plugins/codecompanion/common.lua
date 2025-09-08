--- Common parts of my personal/work CodeCompanion configuration live here.

local slash_cmds = require("plugins.codecompanion.slash_cmds")

local M = {}

--- Common lazy.nvim plugin configuration for CodeCompanion that is shared between my personal and
--- work configurations.
M.common_plugin_config = {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		"olimorris/codecompanion.nvim",
		version = "*",
		dependencies = {
			{ "nvim-lua/plenary.nvim", branch = "master" },
			"nvim-treesitter/nvim-treesitter",
			-- For fidget.nvim Integration...
			"j-hui/fidget.nvim",
			-- For better diffs...
			{
				"echasnovski/mini.diff",
				config = function()
					local diff = require("mini.diff")
					diff.setup({
						-- Disabled by default
						source = diff.gen_source.none(),
					})
				end,
			},
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
		opts = M.common_setup_opts,
	},
}

--- Common setup() options for CodeCompanion that are shared between my personal and work
--- configurations.
M.common_setup_opts = {
	display = {
		chat = {
			show_settings = true,
		},
		diff = {
			provider = "mini_diff",
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
			keymaps = {
				close = { modes = { n = "q", i = "<c-c>" } },
				completion = {
					modes = {
						i = "<c-d>",
					},
				},
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
							i = "<c-b>",
							n = "gb",
						},
					},
				},
				favs = slash_cmds.favs,
				file = {
					keymaps = {
						modes = {
							i = "<c-g>f",
							n = "gF",
						},
					},
				},
				load_group = slash_cmds.load_group,
				save_group = slash_cmds.save_group,
				workspace = {
					keymaps = {
						modes = {
							i = "<c-w>",
							n = "gw",
						},
					},
				},
			},
		},
		inline = {
			keymaps = {
				accept_change = {
					modes = { n = "<leader>ca" }, -- Remember this as (A)ccept
				},
				reject_change = {
					modes = { n = "<leader>cr" }, -- Remember this as (R)eject
				},
				always_accept = {
					modes = { n = "<leader>cy" }, -- Remember this as (Y)olo
				},
			},
		},
	},
}

--- CodeCompanion init() code that is common to both my personal and work configurations.
function M.common_init()
	require("extra.codecompanion.fidget").init()
	require("extra.codecompanion.extmarks").setup()

	-- AUTOCMD: Automatically format buffer with conform.nvim after inline request completes.
	vim.api.nvim_create_autocmd({ "User" }, {
		pattern = "CodeCompanionInlineFinished",
		callback = function(request)
			-- Format the buffer after the inline request has completed
			require("conform").format({ bufnr = request.buf })
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
end

--- Create a keymap to switch between primary and secondary adapters for CodeCompanion.
---
--- @param primary_adapter string The primary adapter name
--- @param secondary_adapter string The secondary adapter name
function M.create_adapter_switch_keymap(primary_adapter, secondary_adapter)
	vim.keymap.set("n", "<leader>ccs", function()
		local config = require("codecompanion.config")
		local current = config.strategies.chat.adapter
		local new = current == primary_adapter and secondary_adapter or primary_adapter

		for _, strategy in pairs(config.strategies) do
			strategy.adapter = new
		end

		vim.notify("Switched CodeCompanion adapter to " .. new, vim.log.levels.INFO)
	end, { desc = "Switch AI Adapters (" .. primary_adapter .. " + " .. secondary_adapter .. ")" })
end

return M
