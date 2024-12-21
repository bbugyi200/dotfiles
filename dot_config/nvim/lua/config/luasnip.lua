local ls = require("luasnip").config.setup({ enable_autosnippets = true, store_selection_keys = "<Tab>" })

vim.keymap.set({ "i" }, "<C-K>", function()
	ls.expand()
end, { silent = true })

require("luasnip.loaders.from_lua").load({ paths = "~/.config/nvim/snippets" })
