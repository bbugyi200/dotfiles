--- Neovim file explorer: edit your filesystem like a buffer

return {
	-- PLUGIN: http://github.com/stevearc/oil.nvim
	{
		"stevearc/oil.nvim",
		opts = { default_file_explorer = false },
		init = function()
			-- KEYMAP(C): o   (:o<cr> --> :Oil<cr>)
			vim.cmd([[
        cnoreabbrev o <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Oil" : "o"<CR>
      ]])

			-- AUTOCMD: Add 'q' keymap to exit ':Oil' buffers.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "oil" },
				callback = function()
					-- KEYMAP(N): q
					vim.keymap.set("n", "q", function()
						local listed_buffer_info = vim.fn.getbufinfo({ buflisted = 1 })
						if #listed_buffer_info ~= 0 then
							vim.cmd("b#")
						else
							vim.cmd("q")
						end
					end, { buffer = true, desc = "Close the current :Oil buffer." })
				end,
			})
		end,
	},
}
