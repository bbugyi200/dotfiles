--- Clarify and beautify your comments and plain text files using boxes and lines.

return {
	-- PLUGIN: http://github.com/LudoPinelli/comment-box.nvim
	{
		"LudoPinelli/comment-box.nvim",
		init = function()
			require("which-key").add({ "<leader>cb", group = "Comment Box", mode = { "n", "v" } })

			-- KEYMAP(N): <leader>cbb
			vim.keymap.set({ "n", "v" }, "<leader>cbb", "<cmd>CBlcbox<cr>", {
				desc = "Wrap selected / current line(s) in box comment.",
			})
			-- KEYMAP(N): <leader>cbd
			vim.keymap.set(
				{ "n", "v" },
				"<leader>cbd",
				"<cmd>CBd<cr>",
				{ desc = "Remove comment box from selected / current line(s)." }
			)
			-- KEYMAP(N): <leader>cbl
			vim.keymap.set("n", "<leader>cbl", "<cmd>CBlcline<cr>", {
				desc = "Wrap current line in in header line comment.",
			})
			-- KEYMAP(N): <leader>cby
			vim.keymap.set({ "n", "v" }, "<leader>cby", "<cmd>CBy<cr>", {
				desc = "Copy text inside of comment box that is selected / on the current line.",
			})
		end,
	},
}
