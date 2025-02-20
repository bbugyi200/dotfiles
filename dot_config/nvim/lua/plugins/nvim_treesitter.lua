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
				incremental_selection = {
					enable = true,
					keymaps = {
						init_selection = "<leader>ii", -- set to `false` to disable one of the mappings
						node_incremental = "iN",
						scope_incremental = "iS",
						node_decremental = "iP",
					},
				},
				textobjects = {
					lsp_interop = {
						enable = true,
						border = "none",
						floating_preview_opts = {},
						peek_definition_code = {
							["<leader>ikc"] = "@class.outer",
							["<leader>ikf"] = "@function.outer",
						},
					},
					move = {
						enable = true,
						set_jumps = true, -- whether to set jumps in the jumplist
						goto_next_start = {
							["]a"] = { query = "@parameter.outer", desc = "Jump to start of next parameter." },
							["]f"] = "@function.outer",
							["]c"] = { query = "@class.outer", desc = "Jump to start of next class." },
						},
						goto_next_end = {
							["]A"] = { query = "@parameter.outer", desc = "Jump to end of next parameter." },
							["]F"] = { query = "@function.outer", desc = "Jump to end of next function." },
							["]C"] = { query = "@class.outer", desc = "Jump to end of next class." },
						},
						goto_previous_start = {
							["[a"] = { query = "@parameter.outer", desc = "Jump to start of previous parameter." },
							["[f"] = { query = "@function.outer", desc = "Jump to start of previous function." },
							["[c"] = { query = "@class.outer", desc = "Jump to start of previous class." },
						},
						goto_previous_end = {
							["[A"] = { query = "@parameter.outer", desc = "Jump to end of previous parameter." },
							["[F"] = { query = "@function.outer", desc = "Jump to end of previous function." },
							["[C"] = { query = "@class.outer", desc = "Jump to end of previous class." },
						},
					},
					select = {
						enable = true,
						-- Automatically jump forward to textobj, similar to targets.vim
						lookahead = true,
						include_surrounding_whitespace = false,
						keymaps = {
							-- You can use the capture groups defined in textobjects.scm
							["aa"] = { query = "@parameter.outer", desc = "Select outer part of parameter." },
							["ac"] = { query = "@class.outer", desc = "Select outer part of class." },
							["af"] = { query = "@function.outer", desc = "Select outer part of function." },
							["ia"] = { query = "@parameter.inner", desc = "Select inner part of parameter." },
							["ic"] = { query = "@class.inner", desc = "Select inner part of a class region." },
							["if"] = { query = "@function.inner", desc = "Select inner part of function." },
						},
					},
					swap = {
						enable = true,
						swap_next = {
							["<leader>isa"] = {
								query = "@parameter.inner",
								desc = "Swap current arg with the next arg.",
							},
							["<leader>isc"] = {
								query = "@class.outer",
								desc = "Swap current class with the next class.",
							},
							["<leader>isf"] = {
								query = "@function.outer",
								desc = "Swap current function with the next function.",
							},
						},
						swap_previous = {
							["<leader>isA"] = {
								query = "@parameter.inner",
								desc = "Swap current arg with the previous arg.",
							},
							["<leader>isC"] = {
								query = "@class.outer",
								desc = "Swap current class with the previous class.",
							},
							["<leader>isF"] = {
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
		init = function()
			local ts_repeat_move = require("nvim-treesitter.textobjects.repeatable_move")

			-- KEYMAP(N+X+O): ]]
			vim.keymap.set(
				{ "n", "x", "o" },
				"]]",
				ts_repeat_move.repeat_last_move_next,
				{ desc = "Repeat last supported motion (remap of ';')" }
			)
			-- KEYMAP(N+X+O): [[
			vim.keymap.set(
				{ "n", "x", "o" },
				"[[",
				ts_repeat_move.repeat_last_move_previous,
				{ desc = "Repeat last supported motion in opposite direction (remap of ',')" }
			)
			-- Make builtin f, F, t, T also repeatable with ]] and [[.
			vim.keymap.set({ "n", "x", "o" }, "f", ts_repeat_move.builtin_f_expr, { expr = true })
			vim.keymap.set({ "n", "x", "o" }, "F", ts_repeat_move.builtin_F_expr, { expr = true })
			vim.keymap.set({ "n", "x", "o" }, "t", ts_repeat_move.builtin_t_expr, { expr = true })
			vim.keymap.set({ "n", "x", "o" }, "T", ts_repeat_move.builtin_T_expr, { expr = true })
		end,
	},
}
