--- Plugin that allows you to perform web searches directly from within Neovim!

return {
	-- PLUGIN: http://github.com/Aliqyan-21/wit.nvim
	{
		"Aliqyan-21/wit.nvim",
		opts = {},
		init = function()
			local wit = require("wit.core")

			-- COMMAND: WitMoma
			vim.api.nvim_create_user_command("WitMoma", function(opts)
				local url = "https://moma.corp.google.com/search?q=" .. opts.args
				wit.open_url(url)
			end, { nargs = 1 })

			-- COMMAND: WitGitHub
			vim.api.nvim_create_user_command("WitGitHub", function(opts)
				local url = "https://github.com/search?type=code&q=" .. opts.args
				wit.open_url(url)
			end, { nargs = 1 })

			-- KEYMAP(N): <leader>wg
			vim.keymap.set(
				"n",
				"<leader>wg",
				":WitSearch site:github.com ",
				{ desc = "Shortcut for ':WitSearch site:github.com'" }
			)

			-- KEYMAP(N): <leader>wh
			vim.keymap.set("n", "<leader>wh", ":WitGitHub ", { desc = "Shortcut for :WitGitHub" })

			-- KEYMAP(N): <leader>wm
			vim.keymap.set("n", "<leader>wm", ":WitMoma ", { desc = "Shortcut for :WitMoma" })

			-- KEYMAP(N): <leader>ww
			vim.keymap.set("n", "<leader>ww", ":WitSearch ", { desc = "Shortcut for :WitSearch" })
		end,
	},
}
