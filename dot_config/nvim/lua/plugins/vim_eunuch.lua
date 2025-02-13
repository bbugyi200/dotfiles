--- Vim sugar for the UNIX shell commands that need it the most.

--- Type ':Move <path>' to make it easier to rename files quickly.
---
---@param path string The ':Move' command's argument will be prepopulated with this path.
local function preload_move_command(path)
	vim.api.nvim_feedkeys(":Move " .. path, "n", true)
end

return {
	-- PLUGIN: http://github.com/tpope/vim-eunuch
	{
		"tpope/vim-eunuch",
		init = function()
			vim.g.eunuch_interpreters = {
				-- Allows me to enter '#!<cr>' at the top of a file to insert
				-- '#!/bin/bash' and make the file executable!
				["."] = "/bin/bash",
			}

			-- KEYMAP(N): <leader>md
			vim.keymap.set("n", "<leader>md", function()
				preload_move_command(vim.fn.expand("%:h") .. "/")
			end, { desc = "Shortcut for ':Move <path>/'" })
			-- KEYMAP(N): <leader>me
			vim.keymap.set("n", "<leader>me", function()
				preload_move_command(vim.fn.expand("%:r"))
			end, { desc = "Shortcut for ':Move <path>/<stem>'" })
			-- KEYMAP(N): <leader>mm
			vim.keymap.set("n", "<leader>mm", ":Move ", { desc = "Shortcut for ':Move'" })
			-- KEYMAP(N): <leader>mp
			vim.keymap.set("n", "<leader>mp", function()
				preload_move_command(vim.fn.expand("%"))
			end, { desc = "Shortcut for ':Move <path>/<stem>.<ext>'" })
		end,
	},
}
