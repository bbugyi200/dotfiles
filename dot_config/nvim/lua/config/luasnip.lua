local types = require("luasnip.util.types")
require("luasnip").config.setup({
	enable_autosnippets = true,
	store_selection_keys = "<Tab>",
	ext_opts = {
		[types.choiceNode] = {
			active = {
				virt_text = { { "●", "GruvboxOrange" } },
				priority = 0,
			},
		},
	},
})

vim.keymap.set({ "i", "s" }, "<C-J>", function()
	if require("luasnip").choice_active() then
		require("luasnip").change_choice(1)
	end
end, { silent = true })
vim.keymap.set({ "i", "s" }, "<C-K>", function()
	if require("luasnip").choice_active() then
		require("luasnip").change_choice(-1)
	end
end, { silent = true })

require("luasnip.loaders.from_lua").load({
	paths = "~/.config/nvim/snippets",
	fs_event_providers = { autocmd = true, libuv = true },
})
