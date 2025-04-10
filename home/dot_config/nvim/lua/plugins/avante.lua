--- Use your Neovim like using Cursor AI IDE!

local is_goog_machine = require("util.is_goog_machine")

if is_goog_machine() then
	-- When working from a Google machine, I am not allowed to use external LLM
	-- tools like OpenAI or Anthropic.
	return {}
else
	return {
		-- PLUGIN: http://github.com/yetone/avante.nvim
		{
			"yetone/avante.nvim",
			build = "make",
			dependencies = {
				"nvim-treesitter/nvim-treesitter",
				"stevearc/dressing.nvim",
				"nvim-lua/plenary.nvim",
				"MunifTanjim/nui.nvim",
			},
			event = "VeryLazy",
			version = false,
			opts = {
				provider = "claude",
				behaviour = {
					auto_set_keymaps = false,
				},
				claude = {
					api_key_name = { "pass", "show", "claude_nvim_api_key" },
					endpoint = "https://api.anthropic.com",
					model = "claude-3-5-sonnet-20241022",
					temperature = 0,
					max_tokens = 4096,
				},
				openai = {
					api_key_name = { "pass", "show", "chatgpt_nvim_api_key" },
					endpoint = "https://api.openai.com/v1",
					model = "gpt-4o",
					timeout = 30000,
					temperature = 0,
					max_completion_tokens = 8192,
				},
				mappings = {
					ask = "<leader>ava",
					edit = "<leader>ave",
				},
			},
			init = function()
				-- KEYMAP GROUP: <leader>av
				vim.keymap.set({ "n", "v" }, "<leader>av", "<nop>", { desc = "avante.nvim" })

				-- KEYMAP: <leader>ava
				vim.keymap.set({ "n", "v" }, "<leader>ava", "<cmd>AvanteAsk<cr>", { desc = "AvanteAsk" })

				-- KEYMAP: <leader>ave
				vim.keymap.set({ "n", "v" }, "<leader>ave", "<cmd>AvanteEdit<cr>", { desc = "AvanteEdit" })

				-- KEYMAP GROUP: <leader>avp
				vim.keymap.set({ "n", "v" }, "<leader>avp", "<nop>", { desc = "AvanteSwitchProvider" })

				-- KEYMAP: <leader>avpc
				vim.keymap.set(
					{ "n", "v" },
					"<leader>avpc",
					"<cmd>AvanteSwitchProvider claude<cr>",
					{ desc = "AvanteSwitchProvider claude" }
				)

				-- KEYMAP: <leader>avpo
				vim.keymap.set(
					{ "n", "v" },
					"<leader>avpo",
					"<cmd>AvanteSwitchProvider openai<cr>",
					{ desc = "AvanteSwitchProvider openai" }
				)
			end,
		},
	}
end
