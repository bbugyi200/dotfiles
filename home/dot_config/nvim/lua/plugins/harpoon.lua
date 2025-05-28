--- Getting you where you want with the fewest keystrokes.

return {
	-- PLUGIN: http://github.com/ThePrimeagen/harpoon
	{
		"ThePrimeagen/harpoon",
		branch = "harpoon2",
		dependencies = { "nvim-lua/plenary.nvim" },
		opts = {},
		init = function()
			local harpoon = require("harpoon")

			require("telescope").load_extension("harpoon")

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: <leader>th
			vim.keymap.set("n", "<leader>th", "<cmd>Telescope harpoon marks<cr>", {
				desc = "Telescope harpoon marks",
			})

			-- KEYMAP GROUP: <leader>h
			vim.keymap.set("n", "<leader>h", "<nop>", { desc = "harpoon.nvim" })
			-- KEYMAP: <leader>h1
			-- KEYMAP: <leader>h2
			-- KEYMAP: <leader>h3
			-- KEYMAP: <leader>h4
			-- KEYMAP: <leader>h5
			for i = 1, 9 do
				vim.keymap.set("n", "<leader>h" .. i, function()
					harpoon:list():select(i)
				end, { desc = "Navigate to harpoon mark " .. i .. "." })
			end
			-- KEYMAP: <leader>ha
			vim.keymap.set("n", "<leader>ha", function()
				harpoon:list():add()
				vim.notify("Added file to harpoon list: " .. vim.fn.expand("%:t"))
			end, { desc = "Add a new file to harpoon list." })
			-- KEYMAP: <leader>hl
			vim.keymap.set("n", "<leader>hl", function()
				harpoon.ui:toggle_quick_menu(harpoon:list())
			end, { desc = "Select a harpoon mark to navigate to." })
			-- KEYMAP: <leader>hn
			vim.keymap.set("n", "<leader>hn", function()
				harpoon:list():next()
			end, { desc = "Navigate to next harpoon mark." })
			-- KEYMAP: <leader>hp
			vim.keymap.set("n", "<leader>hp", function()
				harpoon:list():prev()
			end, { desc = "Navigate to previous harpoon mark." })
		end,
	},
}
