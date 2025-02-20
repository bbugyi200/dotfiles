--- Helps you win at grep.

local feedkeys = require("util.feedkeys")

return {
	-- PLUGIN: http://github.com/mhinz/vim-grepper
	{
		"mhinz/vim-grepper",
		init = function()
			vim.g.grepper = {
				next_tool = "<leader>g",
				rg = { grepprg = "rg -H --no-heading --vimgrep --smart-case --follow -g '!.git/*'" },
				tools = { "rg", "git" },
			}

			-- KEYMAP(N): <leader>grg
			vim.keymap.set("n", "<leader>grg", function()
				feedkeys(":GrepperGit ")
			end, { desc = "Shortcut to trigger a :GrepperGit prompt." })

			-- KEYMAP(N): <leader>grr
			vim.keymap.set("n", "<leader>grr", function()
				feedkeys(":GrepperRg ")
			end, { desc = "Shortcut to trigger a :GrepperRg prompt." })

			-- KEYMAP(N): <leader>grv
			vim.keymap.set("n", "<leader>grv", function()
				feedkeys(":lvim /")
			end, { desc = "Shortcut to trigger a :lvim prompt." })

			-- KEYMAP(N): <leader>grV
			vim.keymap.set("n", "<leader>grV", function()
				local lvim_glob = "**/*." .. vim.bo.filetype
				feedkeys(":lvim // " .. lvim_glob .. string.rep("<left>", #lvim_glob + 2))
			end, { desc = "Shortcut to trigger a :lvim prompt (using current filetype for glob)" })

			-- KEYMAP(N+X): gs
			vim.keymap.set(
				{ "n", "x" },
				"gs",
				"<Plug>(GrepperOperator)",
				{ desc = "Use Grepper with a textobject / motion." }
			)
		end,
	},
}
