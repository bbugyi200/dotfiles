--- Obsidian vault navigation and search for the bob vault.

return {
	-- PLUGIN: http://github.com/obsidian-nvim/obsidian.nvim
	"obsidian-nvim/obsidian.nvim",
	version = "*",
	cmd = { "Obsidian" },
	ft = { "markdown" },
	opts = {
		legacy_commands = false,
		workspaces = {
			{
				name = "bob",
				path = "~/bob",
			},
		},
		picker = {
			name = "telescope.nvim",
		},
		completion = {
			nvim_cmp = true,
			blink = false,
		},
		daily_notes = {
			folder = nil,
			date_format = "YYYY/YYYYMMDD[_day]",
			default_tags = {},
			workdays_only = false,
		},
		attachments = {
			folder = "img",
		},
		ui = {
			enable = false,
		},
	},
	init = function()
		-- KEYMAP: <leader>mdo
		vim.keymap.set("n", "<leader>mdo", "<cmd>Obsidian quick_switch<cr>", { desc = "Obsidian quick switch" })

		-- KEYMAP: <leader>mds
		vim.keymap.set("n", "<leader>mds", "<cmd>Obsidian search<cr>", { desc = "Obsidian search" })

		-- KEYMAP: <leader>mdd
		vim.keymap.set("n", "<leader>mdd", "<cmd>Obsidian today<cr>", { desc = "Obsidian today" })

		-- KEYMAP: <leader>mdb
		vim.keymap.set("n", "<leader>mdb", "<cmd>Obsidian backlinks<cr>", { desc = "Obsidian backlinks" })

		-- KEYMAP: <leader>mdn
		vim.keymap.set("n", "<leader>mdn", "<cmd>Obsidian new<cr>", { desc = "Obsidian new" })
	end,
}
