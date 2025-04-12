--- Use your Neovim like using Cursor AI IDE!
--
-- P2: Figure out how to get openai provider working! Applying changes wouldn't
--     work last time I checked!

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
				},
				hints = { enabled = false },
				claude = {
					api_key_name = { "pass", "show", "claude_nvim_api_key" },
					model = "claude-3-5-sonnet-20241022",
					temperature = 0,
					max_tokens = 4096,
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
						end, { desc = "Submit Avante query." })

						-- KEYMAP: <c-q>
						vim.keymap.set("i", "<c-q>", function()
							-- Exit insert mode
							vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, true, true), "n", false)
							-- Yank the query to my clipboard.
							vim.cmd("normal! ggyG")
							-- Simulate keypress to tirgger keymap that submits query!
							vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<c-s>", true, true, true), "v", true)
						end, { desc = "Submit Avante query from insert mode." })
					end,
				})
			end,
		},
	}
end
