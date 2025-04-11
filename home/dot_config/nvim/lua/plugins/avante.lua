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
				"nvim-tree/nvim-web-devicons",
			},
			event = "VeryLazy",
			opts = {
				provider = "claude",
				behaviour = {
					auto_set_keymaps = false,
					-- P2: Remove The below line and the 'groq' vendor from this config?
					enable_cursor_planning_mode = false,
				},
				cursor_applying_provider = "groq",
				claude = {
					api_key_name = { "pass", "show", "claude_nvim_api_key" },
				},
				openai = {
					api_key_name = { "pass", "show", "chatgpt_nvim_api_key" },
				},
				mappings = {
					ask = "<leader>ava",
					edit = "<leader>ave",
					sidebar = {
						close_from_input = { normal = "q", insert = "<C-d>" },
					},
				},
				vendors = {
					groq = {
						__inherited_from = "openai",
						api_key_name = { "pass", "show", "groq_nvim_api_key" },
						endpoint = "https://api.groq.com/openai/v1/",
						model = "llama-3.3-70b-versatile",
						max_completion_tokens = 32768,
					},
				},
			},
			init = function()
				-- ╭─────────────────────────────────────────────────────────╮
				-- │                         Keymaps                         │
				-- ╰─────────────────────────────────────────────────────────╯
				-- KEYMAP GROUP: <leader>av
				vim.keymap.set({ "n", "v" }, "<leader>av", "<nop>", { desc = "avante.nvim" })

				-- KEYMAP: <leader>ava
				vim.keymap.set({ "n", "v" }, "<leader>ava", "<cmd>AvanteAsk<cr>", { desc = "AvanteAsk" })

				-- KEYMAP: <leader>ave
				vim.keymap.set({ "n", "v" }, "<leader>ave", "<cmd>AvanteEdit<cr>", { desc = "AvanteEdit" })

				-- KEYMAP: <leader>avh
				vim.keymap.set({ "n", "v" }, "<leader>avh", "<cmd>AvanteHistory<cr>", { desc = "AvanteHistory" })

				-- KEYMAP: <leader>avm
				vim.keymap.set({ "n", "v" }, "<leader>avm", "<cmd>AvanteModels<cr>", { desc = "AvanteModels" })

				-- ────────────────── AvanteSwitchProvider ──────────────────
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
