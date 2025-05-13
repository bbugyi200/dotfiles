--- Single tabpage interface for easily cycling through diffs for all modified files for any git rev.

return {
	-- PLUGIN: http://github.com/sindrets/diffview.nvim
	{
		"sindrets/diffview.nvim",
		opts = {},
		init = function()
			-- KEYMAP: <leader>dv
			vim.keymap.set("n", "<leader>dv", "<cmd>DiffviewOpen<cr>", { desc = "DiffviewOpen" })
		end,
	},
}
