--- Single tabpage interface for easily cycling through diffs for all modified files for any git rev.

return {
	-- PLUGIN: http://github.com/sindrets/diffview.nvim
	{
		"sindrets/diffview.nvim",
		opts = {
			hooks = {
				view_opened = function(_)
					-- KEYMAP: q
					vim.keymap.set("n", "q", "<cmd>DiffviewClose<cr>", { desc = "DiffviewClose" })
				end,
				view_closed = function(_)
					vim.keymap.del("n", "q")
				end,
			},
			view = {
				merge_tool = {
					layout = "diff1_plain",
				},
			},
		},
		init = function()
			-- KEYMAP GROUP: <leader>dv
			vim.keymap.set("n", "<leader>dv", "<nop>", { desc = "diffview.nvim" })
			-- KEYMAP: <leader>dvh
			vim.keymap.set("n", "<leader>dvh", "<cmd>DiffviewFileHistory<cr>", { desc = "DiffviewFileHistory" })
			-- KEYMAP: <leader>dvo
			vim.keymap.set("n", "<leader>dvo", "<cmd>DiffviewOpen<cr>", { desc = "DiffviewOpen" })
		end,
	},
}
