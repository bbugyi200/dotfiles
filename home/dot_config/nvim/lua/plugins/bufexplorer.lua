--- Quickly and easily switch between buffers.

return {
	-- PLUGIN: http://github.com/jlanzarotta/bufexplorer
	{
		"jlanzarotta/bufexplorer",
		dependencies = { "ryanoasis/vim-devicons" },
		init = function()
			vim.g.bufExplorerDisableDefaultKeyMapping = 1
			vim.g.bufExplorerShowRelativePath = 1

			-- KEYMAP: <leader>bu
			vim.keymap.set("n", "<leader>bu", "<cmd>BufExplorer<cr>", { desc = "BufExplorer" })
		end,
	},
}
