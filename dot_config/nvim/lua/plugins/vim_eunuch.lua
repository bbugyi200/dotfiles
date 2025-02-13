--- Vim sugar for the UNIX shell commands that need it the most.

local feedkeys = require("util.feedkeys")

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
				feedkeys(":Move " .. vim.fn.expand("%:h") .. "/")
			end, { desc = "Shortcut for ':Move <dir>/'" })

			-- KEYMAP(N): <leader>mf
			vim.keymap.set("n", "<leader>mf", function()
				feedkeys(":Move " .. vim.fn.expand("%"))
			end, { desc = "Shortcut for ':Move <dir>/<stem>.<ext>'" })

			-- KEYMAP(N): <leader>mF
			vim.keymap.set("n", "<leader>mF", function()
				local basename = vim.fn.expand("%:t")
				feedkeys(":Move " .. vim.fn.expand("%") .. string.rep("<left>", string.len(basename)))
			end, { desc = "Shortcut for ':Move <dir>/<stem>.<ext>' (with cursor moved to before <stem>)" })

			-- KEYMAP(N): <leader>me
			vim.keymap.set("n", "<leader>me", function()
				feedkeys(":Move " .. vim.fn.expand("%:r"))
			end, { desc = "Shortcut for ':Move <dir>/<stem>'" })

			-- KEYMAP(C): cp
			vim.cmd('cabbrev cp <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Copy" : "cp"<CR>')
			-- KEYMAP(C): mv
			vim.cmd('cabbrev mv <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Move" : "mv"<CR>')
		end,
	},
}
