--- A hackable & fancy vimdoc/help file viewer for Neovim

return {
	-- PLUGIN: http://github.com/OXY2DEV/helpview.nvim
	{
		"OXY2DEV/helpview.nvim",
		lazy = false,
		init = function()
			-- AUTOCMD: Configuration that is specific to 'help' buffers.
			vim.api.nvim_create_autocmd("BufWinEnter", {
				callback = function()
					-- Abort if the buffer is not a help buffer.
					if vim.bo.buftype ~= "help" then
						return
					end

					-- KEYMAP: <leader>H
					vim.keymap.set("n", "<leader>H", "<cmd>Helpview toggle<cr>", { desc = "Toggle helpview.nvim." })
				end,
			})
		end,
	},
}
