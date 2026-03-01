--- File manager for Neovim powered by nnn.

return {
	-- PLUGIN: http://github.com/luukvbaal/nnn.nvim
	{
		"luukvbaal/nnn.nvim",
		cmd = { "NnnPicker", "NnnExplorer" },
		keys = {
			-- KEYMAP: <leader>-
			{ "<leader>-", "<cmd>NnnPicker %p:h<cr>", desc = "Pick a local file with `nnn`." },
			-- KEYMAP: <leader>nn
			{ "<leader>nn", "<cmd>NnnPicker<cr>", desc = "Pick a CWD file with `nnn`." },
		},
		config = function()
			local builtin = require("nnn").builtin
			require("nnn").setup({
				mappings = {
					{ "<C-t>", builtin.open_in_tab }, -- open file(s) in tab
					{ "<C-s>", builtin.open_in_split }, -- open file(s) in split
					{ "<C-v>", builtin.open_in_vsplit }, -- open file(s) in vertical split
					{ "<C-p>", builtin.open_in_preview }, -- open file in preview split keeping nnn focused
					{ "<C-y>", builtin.copy_to_clipboard }, -- copy file(s) to clipboard
					{ "<C-w>", builtin.cd_to_path }, -- cd to file directory
					{ "<C-e>", builtin.populate_cmdline }, -- populate cmdline (:) with file(s)
				},
			})
		end,
	},
}
