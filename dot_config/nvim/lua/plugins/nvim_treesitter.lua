return {
	"nvim-treesitter/nvim-treesitter",
	build = ":TSUpdate",
	init = function()
		require("nvim-treesitter.configs").setup({
			ensure_installed = {
				"c",
				"bash",
				"dart",
				"git_config",
				"gitcommit",
				"gitignore",
				"html",
				"java",
				"javascript",
				"lua",
				"make",
				"markdown",
				"python",
				"query",
				"rust",
				"toml",
				"vim",
				"vimdoc",
				"yaml",
			},
			sync_install = false,
			highlight = { enable = true, additional_vim_regex_highlighting = false },
			indent = { enable = true },
		})
	end,
}
