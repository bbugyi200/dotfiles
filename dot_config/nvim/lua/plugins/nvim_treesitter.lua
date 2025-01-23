-- P1: Use tree splitter text objects (ex: cif keymap to clear and edit a function body)
--     * Ex: https://github.com/nvim-lua/kickstart.nvim/blob/f6d67b69c3/init.lua#L330-L363
return {
	-- PLUGIN: http://github.com/nvim-treesitter/nvim-treesitter
	{
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
					"markdown_inline",
					"python",
					"query",
					"rst",
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
	},
}
