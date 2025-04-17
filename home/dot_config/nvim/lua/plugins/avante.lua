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
					enable_cursor_planning_mode = true,
				},
				hints = { enabled = false },
				cursor_applying_provider = "groq",
				claude = {
					api_key_name = "cmd:pass show claude_nvim_api_key",
				},
				openai = {
					api_key_name = "cmd:pass show chatgpt_nvim_api_key",
					model = "gpt-4.1-2025-04-14",
				},
				mappings = {
					ask = "<leader>ava",
					edit = "<leader>ave",
					sidebar = {
						close_from_input = { normal = "q", insert = "<C-d>" },
					},
					submit = {
						normal = "<c-s>",
						insert = "<c-s>",
					},
				},
				vendors = {
					groq = {
						__inherited_from = "openai",
						api_key_name = "cmd:pass show groq_nvim_api_key",
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

				-- AUTOCMD: Configure keymaps for AvanteInput buffer.
				vim.api.nvim_create_autocmd("FileType", {
					pattern = { "AvanteInput", "AvantePromptInput" },
					callback = function()
						-- KEYMAP: <cr>
						vim.keymap.set("n", "<cr>", function()
							-- Yank the query to my clipboard.
							vim.cmd("normal! ggyG")
							-- Simulate keypress to tirgger keymap that submits query!
							vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<c-s>", true, true, true), "v", true)
						end, { buffer = true, desc = "Submit Avante query." })

						-- KEYMAP: <c-q>
						vim.keymap.set("i", "<c-q>", function()
							-- Exit insert mode
							vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, true, true), "n", false)
							-- Yank the query to my clipboard.
							vim.cmd("normal! ggyG")
							-- Simulate keypress to tirgger keymap that submits query!
							vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<c-s>", true, true, true), "v", true)
						end, { buffer = true, desc = "Submit Avante query from insert mode." })
					end,
				})

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
