-- P3: Flex on-the-fly luasnip snippets!
-- P3: Configure Lua-Snips
--   [X] Migrate all useful 'all' snippets.
--   [ ] Add snippets for lua (ex: if, elif, ife, funcs, snippets, todo).
--   [ ] Migrate all useful Dart snippets.
--   [ ] Migrate all useful Java snippets.
--   [ ] Migrate all useful Python snippets.
--   [ ] Migrate all useful shell snippets.
--   [ ] Migrate all useful zorg snippets.
--   [ ] Create snippet that replaces `hc`!
return {
	"L3MON4D3/LuaSnip",
	version = "v2.*",
	build = "make install_jsregexp",
	dependencies = {
		"saadparwaiz1/cmp_luasnip",
	},
	init = function()
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
		-- Map to store visual selection of next N lines.
		vim.keymap.set("n", "<leader>v", function()
			return "normal V" .. vim.v.count .. "j<tab>"
		end, { desc = "Map to store visual selection of next N lines." })

		require("luasnip.loaders.from_lua").load({
			lazy_paths = { "~/cfg/luasnippets", vim.fn.getcwd() .. "/luasnippets" },
			fs_event_providers = { autocmd = true, libuv = true },
		})
	end,
}
