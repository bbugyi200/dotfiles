--- Display and search for buganizer bugs.

-- PLUGIN: http://go/buganizer.nvim
return {
	{
		url = "sso://user/rprs/buganizer.nvim",
		dependencies = {
			"nvim-telescope/telescope.nvim",
			{ url = "sso://user/vicentecaycedo/buganizer-utils.nvim" },
		},
		init = function()
			-- KEYMAP GROUP: <leader>bu
			vim.keymap.set("n", "<leader>bu", "<nop>", { desc = "buganizer.nvim" })

			-- KEYMAP: <leader>buf
			vim.keymap.set("n", "<leader>buf", "<cmd>FindBugs<cr>", { desc = "Find bugs." })

			-- KEYMAP: <leader>bui
			vim.keymap.set("n", "<leader>bui", "<cmd>BuganizerSearch<cr>", { desc = "Insert bug ID." })

			-- KEYMAP: <leader>bus
			vim.keymap.set("n", "<leader>bus", "<cmd>ShowBugUnderCursor<cr>", { desc = "Show bug under cursor." })
		end,
	},
}
