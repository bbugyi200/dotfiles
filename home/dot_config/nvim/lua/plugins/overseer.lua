--- A task runner and job management plugin for Neovim.

return {
	-- PLUGIN: http://github.com/stevearc/overseer.nvim
	{
		"stevearc/overseer.nvim",
		opts = {
			strategy = { "toggleterm", direction = "float" },
			templates = { "builtin", "make_targets" },
		},
		init = function()
			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP GROUP: <leader>o
			vim.keymap.set("n", "<leader>o", "<nop>", { desc = "overseer.nvim" })

			-- KEYMAP: <leader>or
			vim.keymap.set("n", "<leader>or", "<cmd>OverseerRun<cr>", { desc = "OverseerRun" })

			-- KEYMAP: <leader>ot
			vim.keymap.set("n", "<leader>ot", "<cmd>OverseerToggle<cr>", { desc = "OverseerToggle" })
		end,
	},
}
