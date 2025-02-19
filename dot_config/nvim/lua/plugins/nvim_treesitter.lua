-- P1: Use tree splitter text objects (ex: cif keymap to clear and edit a function body)
--     * Ex: https://github.com/nvim-lua/kickstart.nvim/blob/f6d67b69c3/init.lua#L330-L363
local treesitter_plugin_name = "nvim-treesitter/nvim-treesitter"
return {
	-- PLUGIN: http://github.com/nvim-treesitter/nvim-treesitter
	{
		treesitter_plugin_name,
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
					move = {
						enable = true,
						set_jumps = true, -- whether to set jumps in the jumplist
						goto_next_start = {
							["]f"] = "@function.outer",
							["]]"] = { query = "@class.outer", desc = "Jump to start of next class." },
							["]s"] = {
								query = "@local.scope",
								query_group = "locals",
								desc = "Jump to start of next local scope.",
							},
							["]z"] = { query = "@fold", query_group = "folds", desc = "Jump to next fold." },
						},
						goto_next_end = {
							["]F"] = { query = "@function.outer", desc = "Jump to end of next function." },
							["]["] = { query = "@class.outer", desc = "Jump to end of next class." },
						},
						goto_previous_start = {
							["[f"] = { query = "@function.outer", desc = "Jump to start of previous function." },
							["[["] = { query = "@class.outer", desc = "Jump to start of previous class." },
						},
						goto_previous_end = {
							["[F"] = { query = "@function.outer", desc = "Jump to end of previous function." },
							["[]"] = { query = "@class.outer", desc = "Jump to end of previous class." },
						},
					},
					select = {
						enable = true,
						-- Automatically jump forward to textobj, similar to targets.vim
						lookahead = true,
						include_surrounding_whitespace = false,
						keymaps = {
							-- You can use the capture groups defined in textobjects.scm
							["af"] = { query = "@function.outer", desc = "Select outer part of function." },
							["if"] = { query = "@function.inner", desc = "Select inner part of function." },
							["ac"] = { query = "@class.outer", desc = "Select outer part of class." },
							["ic"] = { query = "@class.inner", desc = "Select inner part of a class region." },
							["as"] = { query = "@local.scope", query_group = "locals", desc = "Select language scope." },
						},
					},
					swap = {
						enable = true,
						swap_next = {
							["<leader>ia"] = {
								query = "@parameter.inner",
								desc = "Swap current arg with the next arg.",
							},
							["<leader>if"] = {
								query = "@function.outer",
								desc = "Swap current function with the next function.",
							},
						},
						swap_previous = {
							["<leader>iA"] = {
								query = "@parameter.inner",
								desc = "Swap current arg with the previous arg.",
							},
							["<leader>iF"] = {
								query = "@function.outer",
								desc = "Swap current function with the previous function.",
							},
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
		dependencies = treesitter_plugin_name,
	},
}
