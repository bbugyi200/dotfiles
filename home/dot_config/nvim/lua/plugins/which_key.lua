--- which-key
---
--- Create key bindings that stick. WhichKey helps you remember your Neovim
--- keymaps, by showing available keybindings in a popup as you type.

return {
	-- PLUGIN: http://github.com/folke/which-key.nvim
	{
		"folke/which-key.nvim",
		event = "VeryLazy",
		opts = {
			delay = 100,
			preset = "modern",
			triggers = {
				{ "<auto>", mode = "nxso" },
				-- netrw buffers define many m* keymaps
				{ "m", mode = "nxso" },
				-- d* keymaps are defined when nvim-dap sessions are active
				{ "d", mode = "nxso" },
			},
		},
		keys = {
			{
				"<leader>?",
				function()
					require("which-key").show({ global = false })
				end,
				desc = "Buffer Local Keymaps (which-key)",
			},
		},
		init = function()
			local wk = require("which-key")

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: [[
			vim.keymap.set("n", "[[", function()
				wk.show({ keys = "[", loop = true })
			end, { desc = "Enable hydra-mode for '[' key." })

			-- KEYMAP: ]]
			vim.keymap.set("n", "]]", function()
				wk.show({ keys = "]", loop = true })
			end, { desc = "Enable hydra-mode for ']' key." })

			-- ╭─────────────────────────────────────────────────────────╮
			-- │       KEYMAP GROUPS that have nowhere else to go        │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP GROUP: <leader>md
			vim.keymap.set("n", "<leader>md", "<nop>", { desc = "Markdown" })
		end,
	},
}
