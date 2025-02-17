-- P1: Use tree splitter text objects (ex: cif keymap to clear and edit a function body)
--     * Ex: https://github.com/nvim-lua/kickstart.nvim/blob/f6d67b69c3/init.lua#L330-L363
return {
	-- PLUGIN: http://github.com/nvim-treesitter/nvim-treesitter
	{
		"nvim-treesitter/nvim-treesitter",
		build = ":TSUpdate",
		init = function()
			require("nvim-treesitter.configs").setup({
				auto_install = true,
				ignore_install = {},
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
					"scss",
					"toml",
					"vim",
					"vimdoc",
					"yaml",
				},
				sync_install = false,
				textobjects = {
					swap = {
						enable = true,
						swap_next = {
							["<leader>ia"] = "@parameter.inner",
						},
						swap_previous = {
							["<leader>iA"] = "@parameter.inner",
						},
					},
				},
				highlight = { enable = true, additional_vim_regex_highlighting = false },
				indent = { enable = true },
				matchup = { enable = true },
				modules = {},
			})
		end,
	},
	-- PLUGIN: http://github.com/nvim-treesitter/nvim-treesitter-textobjects
	{
		"nvim-treesitter/nvim-treesitter-textobjects",
	},
}
