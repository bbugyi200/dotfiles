--- Vim and Neovim plugin to reveal the commit messages under the cursor.

return {
	-- PLUGIN: http://github.com/rhysd/git-messenger.vim
	{
		"rhysd/git-messenger.vim",
		init = function()
			vim.g.git_messenger_no_default_mappings = 1
			-- KEYMAP: <leader>gm
			vim.keymap.set("n", "<leader>gm", "<cmd>GitMessenger<cr>", { desc = "GitMessenger" })
		end,
	},
}
