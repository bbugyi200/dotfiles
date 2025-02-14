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
			-- Show which-key keymap previews imediately instead of delaying.
			delay = 0,
			preset = "modern",
			triggers = {
				{ "<auto>", mode = "nxso" },
				-- WARNING: This enables which-key keymap previews for m* and q*
				-- keymaps (ex: used by netrw), but for some reason, in the case of q*
				-- keymaps, which-key first needs to be triggered using a different key
				-- (ex: ',' or 'm').
				{ "m", mode = "nxso" },
				{ "q", mode = "nxso" },
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
	},
}
