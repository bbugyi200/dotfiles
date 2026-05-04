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
		init = function()
			vim.g.loaded_zorg_nvim = 1
		end,
		config = function()
			require("zorg").setup({
				cli = {
					command = executable_or_fallback("~/projects/github/zettel-org/zorg/target/debug/zorg", "zorg"),
				},
				mappings = {
					enabled = true,
					prefix = "<leader>z",
					keys = {
						capture = "c",
						export_current = "e",
						fix = "f",
						index = "r",
						open = "o",
						query = "q",
						status = "s",
						watch_start = "w",
						watch_status = "S",
						watch_stop = "W",
					},
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
