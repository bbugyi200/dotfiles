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

-- Map to switch to next luasnip choice.
vim.keymap.set({ "i", "s" }, "<C-J>", function()
	if require("luasnip").choice_active() then
		require("luasnip").change_choice(1)
	end
end, { silent = true })
-- Map to switch to prev luasnip choice.
vim.keymap.set({ "i", "s" }, "<C-K>", function()
	if require("luasnip").choice_active() then
		require("luasnip").change_choice(-1)
	end
end, { silent = true })

require("luasnip.loaders.from_lua").load({
	lazy_paths = { "~/cfg/luasnippets", vim.fn.getcwd() .. "/luasnippets" },
	fs_event_providers = { autocmd = true, libuv = true },
})
