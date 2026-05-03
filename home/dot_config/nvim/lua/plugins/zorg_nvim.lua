local function executable_or_fallback(local_path, fallback)
	local expanded = vim.fn.expand(local_path)
	if vim.fn.executable(expanded) == 1 then
		return expanded
	end

	return fallback
end

return {
	{
		"zettel-org/zorg-nvim",
		config = function()
			require("zorg").setup({
				cli = {
					command = executable_or_fallback("~/projects/github/zettel-org/zorg/target/debug/zorg", "zorg"),
				},
				mappings = {
					enabled = false,
				},
				lsp = {
					command = {
						executable_or_fallback("~/projects/github/zettel-org/zorg/target/debug/zorg-ls", "zorg-ls"),
					},
				},
			})
		end,
	},
}
