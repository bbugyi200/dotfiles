--- Load google paths like //google/* when opening files. Also works with `gf`,
--- although in mosts cases, running `vim.lsp.buf.definition()` (by default
--- mapped to `gd`) over a path will also take you to the file

-- PLUGIN: http://go/googlepaths.nvim
return {
	{
		url = "sso://user/fentanes/googlepaths.nvim",
		event = { #vim.fn.argv() > 0 and "VeryLazy" or "UIEnter", "BufReadCmd //*", "BufReadCmd google3/*" },
		opts = {},
	},
}
