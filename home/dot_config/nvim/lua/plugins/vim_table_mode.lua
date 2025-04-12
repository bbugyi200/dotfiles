--- An awesome automatic table creator & formatter allowing one to create neat tables as you type.

return {
	-- PLUGIN: http://github.com/dhruvasagar/vim-table-mode
	{
		"dhruvasagar/vim-table-mode",
		init = function()
			vim.g.table_mode_disable_mappings = 1
			vim.g.table_mode_disable_tableize_mappings = 1
			vim.g.table_mode_corner_corner = "+"
			vim.g.table_mode_header_fillchar = "="

			-- KEYMAP: <leader>mdt
			vim.keymap.set({ "i", "n" }, "<leader>mdt", "<cmd>TableModeToggle<cr>", {
				desc = "Toggle vim-table-mode.",
			})
		end,
	},
}
