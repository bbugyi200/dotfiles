--- Helps you win at grep.

local feedkeys = require("util.feedkeys")

return {
	-- PLUGIN: http://github.com/mhinz/vim-grepper
	{
		"mhinz/vim-grepper",
		init = function()
			vim.g.grepper = {
				cs = { grepprg = "cs --local --stats=0", grepformat = "%f:%l:%m" },
				next_tool = "<leader>g",
				quickfix = 0, -- Use location list instead of quickfix list.
				rg = { grepprg = "rg -H --hidden --no-heading --vimgrep --smart-case --follow" },
				-- NOTE: The order of tools is important, as the first one is the default.
				tools = { "rg", "git", "cs" },
			}

			-- KEYMAP(N): <leader>grc
			vim.keymap.set("n", "<leader>grc", function()
				feedkeys(":GrepperCs ")
			end, { desc = "Shortcut to trigger a :GrepperCs prompt." })

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
				local filetype_ext = {
					["sh.chezmoitmpl"] = "tmpl",
					bash = "sh",
					python = "py",
					javascript = "js",
					typescript = "ts",
					zorg = "zo",
					-- Add more mappings as needed
				}
				local ext = filetype_ext[vim.bo.filetype] or vim.bo.filetype
				local lvim_rhs = "/ **/*." .. ext .. " | lopen"
				feedkeys(":lvim /" .. lvim_rhs .. string.rep("<left>", #lvim_rhs))
			end, { desc = "Shortcut to trigger a :lvim prompt (using current filetype for glob)" })

			-- KEYMAP(N): <leader>grV
			vim.keymap.set("n", "<leader>grV", function()
				local lvim_rhs = " | lopen"
				feedkeys(":lvim /" .. lvim_rhs .. string.rep("<left>", #lvim_rhs))
			end, { desc = "Shortcut to trigger a :lvim prompt." })

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
