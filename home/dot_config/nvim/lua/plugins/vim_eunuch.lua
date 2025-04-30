--- Vim sugar for the UNIX shell commands that need it the most.

local feedkeys = require("bb_utils.feedkeys")

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

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP GROUP: <leader>cp
			vim.keymap.set("n", "<leader>cp", "<nop>", { desc = "Copy File" })
			-- KEYMAP GROUP: <leader>mv
			vim.keymap.set("n", "<leader>mv", "<nop>", { desc = "Move File" })
			for _, pair in ipairs({ { "cp", "Copy" }, { "mv", "Move" } }) do
				local lhs_group_prefix = pair[1]
				local command = pair[2]

				-- KEYMAP: <leader>cd
				-- KEYMAP: <leader>md
				vim.keymap.set("n", "<leader>" .. lhs_group_prefix .. "d", function()
					feedkeys(":" .. command .. " " .. vim.fn.expand("%:h") .. "/")
				end, { desc = "Shortcut for ':" .. command .. " <dir>/'" })

				-- KEYMAP: <leader>ce
				-- KEYMAP: <leader>me
				vim.keymap.set("n", "<leader>" .. lhs_group_prefix .. "e", function()
					feedkeys(":" .. command .. " " .. vim.fn.expand("%:r"))
				end, { desc = "Shortcut for ':" .. command .. " <dir>/<stem>'" })

				-- KEYMAP: <leader>cf
				-- KEYMAP: <leader>mf
				vim.keymap.set("n", "<leader>" .. lhs_group_prefix .. "f", function()
					feedkeys(":" .. command .. " " .. vim.fn.expand("%"))
				end, { desc = "Shortcut for ':" .. command .. " <dir>/<stem>.<ext>'" })

				-- KEYMAP: <leader>cF
				-- KEYMAP: <leader>mF
				vim.keymap.set("n", "<leader>" .. lhs_group_prefix .. "F", function()
					local basename = vim.fn.expand("%:t")
					feedkeys(":" .. command .. " " .. vim.fn.expand("%") .. string.rep("<left>", string.len(basename)))
				end, {
					desc = "Shortcut for ':" .. command .. " <dir>/<stem>.<ext>' (with cursor moved to before <stem>)",
				})
			end

			-- KEYMAP: cp   (:cp<space> --> :Copy<space>)
			vim.cmd('cnoreabbrev cp <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Copy" : "cp"<CR>')
			-- KEYMAP: mv   (:mv<space> --> :Move<space>)
			vim.cmd('cnoreabbrev mv <c-r>=getcmdpos() == 1 && getcmdtype() == ":" ? "Move" : "mv"<CR>')
		end,
	},
}
