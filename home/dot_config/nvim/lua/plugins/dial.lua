--- Enhanced increment/decrement plugin for Neovim.

return {
	-- PLUGIN: http://github.com/monaqa/dial.nvim
	{
		"monaqa/dial.nvim",
		init = function()
			local augend = require("dial.augend")
			require("dial.config").augends:register_group({
				default = {
					augend.integer.alias.decimal,
					augend.integer.alias.hex,
					augend.integer.alias.binary,
					augend.date.new({
						pattern = "%Y/%m/%d",
						default_kind = "day",
					}),
					augend.date.new({
						pattern = "%Y-%m-%d",
						default_kind = "day",
					}),
					augend.date.new({
						pattern = "%y%m%d@%H%M",
						default_kind = "day",
						only_valid = true,
					}),
					augend.date.new({
						pattern = "%m/%d",
						default_kind = "day",
						only_valid = true,
					}),
					augend.date.new({
						pattern = "%H:%M",
						default_kind = "day",
						only_valid = true,
					}),
					augend.constant.alias.bool,
					augend.constant.alias.semver,
				},
			})
			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: <C-a>
			vim.keymap.set("n", "<C-a>", function()
				require("dial.map").manipulate("increment", "normal")
			end, { desc = "Increment value under cursor" })
			-- KEYMAP: <C-x>
			vim.keymap.set("n", "<C-x>", function()
				require("dial.map").manipulate("decrement", "normal")
			end, { desc = "Decrement value under cursor" })
			-- KEYMAP: g<C-a>
			vim.keymap.set("n", "g<C-a>", function()
				require("dial.map").manipulate("increment", "gnormal")
			end, { desc = "Increment consecutive values" })
			-- KEYMAP: g<C-x>
			vim.keymap.set("n", "g<C-x>", function()
				require("dial.map").manipulate("decrement", "gnormal")
			end, { desc = "Decrement consecutive values" })
			-- KEYMAP: <C-a>
			vim.keymap.set("v", "<C-a>", function()
				require("dial.map").manipulate("increment", "visual")
			end, { desc = "Increment selected value(s)" })
			-- KEYMAP: <C-x>
			vim.keymap.set("v", "<C-x>", function()
				require("dial.map").manipulate("decrement", "visual")
			end, { desc = "Decrement selected value(s)" })
			-- KEYMAP: g<C-a>
			vim.keymap.set("v", "g<C-a>", function()
				require("dial.map").manipulate("increment", "gvisual")
			end, { desc = "Increment consecutive selected values" })
			-- KEYMAP: g<C-x>
			vim.keymap.set("v", "g<C-x>", function()
				require("dial.map").manipulate("decrement", "gvisual")
			end, { desc = "Decrement consecutive selected values" })
		end,
	},
}
