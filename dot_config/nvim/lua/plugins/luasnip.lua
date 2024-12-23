return {
	"L3MON4D3/LuaSnip",
	version = "v2.*",
	build = "make install_jsregexp",
	dependencies = {
		"saadparwaiz1/cmp_luasnip",
		{
			"L3MON4D3/cmp-luasnip-choice",
			config = function()
				require("cmp_luasnip_choice").setup({ auto_open = true })
			end,
		},
	},
}
