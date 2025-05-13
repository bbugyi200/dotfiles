--- Single tabpage interface for easily cycling through diffs for all modified files for any git rev.

return {
	-- PLUGIN: http://github.com/sindrets/diffview.nvim
	{
		"sindrets/diffview.nvim",
		opts = {
			hooks = {
				view_opened = function(_)
					-- KEYMAP: q
					vim.keymap.set("n", "q", "<cmd>tabclose<cr>", { desc = "Close diffview." })
				end,
				view_closed = function(_)
					vim.keymap.del("n", "q")
				end,
			},
		},
		init = function()
			-- KEYMAP: <leader>dv
			vim.keymap.set("n", "<leader>dv", "<cmd>DiffviewOpen<cr>", { desc = "DiffviewOpen" })
		end,
	},
}
