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

			for _, pair in ipairs({ { "c", "Copy" }, { "m", "Move" } }) do
				local char = pair[1]
				local command = pair[2]

				-- KEYMAP(N): <leader>cd
				-- KEYMAP(N): <leader>md
				vim.keymap.set("n", "<leader>" .. char .. "d", function()
					feedkeys(":" .. command .. " " .. vim.fn.expand("%:h") .. "/")
				end, { desc = "Shortcut for ':" .. command .. " <dir>/'" })

				-- KEYMAP(N): <leader>cf
				-- KEYMAP(N): <leader>mf
				vim.keymap.set("n", "<leader>" .. char .. "f", function()
					feedkeys(":" .. command .. " " .. vim.fn.expand("%"))
				end, { desc = "Shortcut for ':" .. command .. " <dir>/<stem>.<ext>'" })

				-- KEYMAP(N): <leader>cF
				-- KEYMAP(N): <leader>mF
				vim.keymap.set(
					"n",
					"<leader>" .. char .. "F",
					function()
						local basename = vim.fn.expand("%:t")
						feedkeys(
							":" .. command .. " " .. vim.fn.expand("%") .. string.rep("<left>", string.len(basename))
						)
					end,
					{
						desc = "Shortcut for ':"
							.. command
							.. " <dir>/<stem>.<ext>' (with cursor moved to before <stem>)",
					}
				)

				-- KEYMAP(N): <leader>ce
				-- KEYMAP(N): <leader>me
				vim.keymap.set("n", "<leader>" .. char .. "e", function()
					feedkeys(":" .. command .. " " .. vim.fn.expand("%:r"))
				end, { desc = "Shortcut for ':" .. command .. " <dir>/<stem>'" })
			end

			-- KEYMAP(C): cp
			vim.cmd('cnoreabbrev cp <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Copy" : "cp"<CR>')
			-- KEYMAP(C): mv
			vim.cmd('cnoreabbrev mv <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Move" : "mv"<CR>')
		end,
	},
}
