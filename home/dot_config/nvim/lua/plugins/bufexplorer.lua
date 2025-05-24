--- Quickly and easily switch between buffers.

return {
	-- PLUGIN: http://github.com/jlanzarotta/bufexplorer
	{
		"jlanzarotta/bufexplorer",
		init = function()
			vim.g.bufExplorerDisableDefaultKeyMapping = 1

			-- KEYMAP: <leader>b
			vim.keymap.set("n", "<leader>b", "<cmd>BufExplorer<cr>", { desc = "BufExplorer" })
		end,
	},
}
