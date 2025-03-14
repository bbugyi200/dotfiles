--- Helping you find free keybinds in Neovim.

return {
	-- PLUGIN: http://github.com/meznaric/key-analyzer.nvim
	{
		"meznaric/key-analyzer.nvim",
		opts = {},
		init = function()
			-- KEYMAP(N): <leader>k
			vim.keymap.set("n", "<leader>k", ":KeyAnalyzer ", { desc = "Shortcut for :KeyAnalyzer." })
		end,
	},
}
