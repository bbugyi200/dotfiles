--- File manager for Neovim powered by nnn.

return {
	-- PLUGIN: http://github.com/luukvbaal/nnn.nvim
	{
		"luukvbaal/nnn.nvim",
		opts = {},
		init = function()
			-- KEYMAP: <leader>-
			vim.keymap.set("n", "<leader>-", "<cmd>NnnPicker %p:h<cr>", { desc = "Pick a local file with `nnn`." })
			-- KEYMAP: <leader>nn
			vim.keymap.set("n", "<leader>nn", "<cmd>NnnPicker<cr>", { desc = "Pick a CWD file with `nnn`." })
		end,
	},
}
