--- File manager for Neovim powered by nnn.

return {
	-- PLUGIN: http://github.com/luukvbaal/nnn.nvim
	{
		"luukvbaal/nnn.nvim",
		opts = {},
		init = function()
			-- KEYMAP: <leader>nn
			vim.keymap.set("n", "<leader>nn", "<cmd>NnnPicker<cr>", { desc = "Pick a file with `nnn`." })
		end,
	},
}
