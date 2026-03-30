-- P1: Use tree splitter text objects (ex: cif keymap to clear and edit a function body)
--     * Ex: https://github.com/nvim-lua/kickstart.nvim/blob/f6d67b69c3/init.lua#L330-L363
local treesitter_plugin_name = "nvim-treesitter/nvim-treesitter"
return {
	-- PLUGIN: http://github.com/nvim-treesitter/nvim-treesitter
	{
		treesitter_plugin_name,
		build = ":TSUpdate",
		dependencies = {
			-- Since require('nvim-dap-repl-highlights').setup() needs to be called
			-- before dap_repl is recognized by treesitter!
			"LiadOz/nvim-dap-repl-highlights",
		},
		opts = {
			auto_install = true,
			ensure_installed = {
				"angular",
				"c",
				"bash",
				"dap_repl",
				"dart",
				"git_config",
				"gitcommit",
				"gitignore",
				"html",
				"java",
				"javascript",
				"just",
				"jinja",
				"jinja_inline",
				"latex",
				"lua",
				"make",
				"markdown",
				"markdown_inline",
				"muttrc",
				"python",
				"query",
				"rst",
				"rust",
				"scss",
				"toml",
				"vim",
				"vimdoc",
				"yaml",
				"zathurarc",
			},
			incremental_selection = {
				enable = true,
				keymaps = {
					init_selection = "<leader>iv", -- set to `false` to disable one of the mappings
					node_incremental = "iN",
					scope_incremental = "iS",
					node_decremental = "iP",
				},
			},
		},
		init = function()
			-- KEYMAP: <leader>iii
			vim.keymap.set("n", "<leader>iii", "<cmd>Inspect<cr>", { desc = "Run :Inspect command." })

			-- KEYMAP: <leader>iit
			vim.keymap.set("n", "<leader>iit", "<cmd>InspectTree<cr>", { desc = "Run :InspectTree command." })

			-- Enable markview preview for octo.nvim and buganizer files!
			vim.treesitter.language.register("markdown", "octo")
			vim.treesitter.language.register("markdown", "bugged")
		end,
	},
	-- PLUGIN: http://github.com/nvim-treesitter/nvim-treesitter-textobjects
	{
		"nvim-treesitter/nvim-treesitter-textobjects",
		dependencies = treesitter_plugin_name,
		config = function()
			require("nvim-treesitter-textobjects").setup({
				select = {
					lookahead = true,
					include_surrounding_whitespace = false,
				},
				move = {
					set_jumps = true,
				},
			})

			local ts_select = require("nvim-treesitter-textobjects.select")
			local ts_move = require("nvim-treesitter-textobjects.move")
			local ts_swap = require("nvim-treesitter-textobjects.swap")
			local ts_repeat_move = require("nvim-treesitter-textobjects.repeatable_move")

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                     Select keymaps                      │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: aa
			vim.keymap.set({ "x", "o" }, "aa", function()
				ts_select.select_textobject("@parameter.outer", "textobjects")
			end, { desc = "Select outer part of parameter." })
			-- KEYMAP: ac
			vim.keymap.set({ "x", "o" }, "ac", function()
				ts_select.select_textobject("@class.outer", "textobjects")
			end, { desc = "Select outer part of class." })
			-- KEYMAP: af
			vim.keymap.set({ "x", "o" }, "af", function()
				ts_select.select_textobject("@function.outer", "textobjects")
			end, { desc = "Select outer part of function." })
			-- KEYMAP: ia
			vim.keymap.set({ "x", "o" }, "ia", function()
				ts_select.select_textobject("@parameter.inner", "textobjects")
			end, { desc = "Select inner part of parameter." })
			-- KEYMAP: ic
			vim.keymap.set({ "x", "o" }, "ic", function()
				ts_select.select_textobject("@class.inner", "textobjects")
			end, { desc = "Select inner part of a class region." })
			-- KEYMAP: if
			vim.keymap.set({ "x", "o" }, "if", function()
				ts_select.select_textobject("@function.inner", "textobjects")
			end, { desc = "Select inner part of function." })

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                      Move keymaps                       │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: ]a
			vim.keymap.set({ "n", "x", "o" }, "]a", function()
				ts_move.goto_next_start("@parameter.outer")
			end, { desc = "Jump to start of next parameter." })
			-- KEYMAP: ]f
			vim.keymap.set({ "n", "x", "o" }, "]f", function()
				ts_move.goto_next_start("@function.outer")
			end, { desc = "Jump to start of next function." })
			-- KEYMAP: g]a
			vim.keymap.set({ "n", "x", "o" }, "g]a", function()
				ts_move.goto_next_end("@parameter.outer")
			end, { desc = "Jump to end of next parameter." })
			-- KEYMAP: g]f
			vim.keymap.set({ "n", "x", "o" }, "g]f", function()
				ts_move.goto_next_end("@function.outer")
			end, { desc = "Jump to end of next function." })
			-- KEYMAP: [a
			vim.keymap.set({ "n", "x", "o" }, "[a", function()
				ts_move.goto_previous_start("@parameter.outer")
			end, { desc = "Jump to start of previous parameter." })
			-- KEYMAP: [f
			vim.keymap.set({ "n", "x", "o" }, "[f", function()
				ts_move.goto_previous_start("@function.outer")
			end, { desc = "Jump to start of previous function." })
			-- KEYMAP: g[a
			vim.keymap.set({ "n", "x", "o" }, "g[a", function()
				ts_move.goto_previous_end("@parameter.outer")
			end, { desc = "Jump to end of previous parameter." })
			-- KEYMAP: g[f
			vim.keymap.set({ "n", "x", "o" }, "g[f", function()
				ts_move.goto_previous_end("@function.outer")
			end, { desc = "Jump to end of previous function." })

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                      Swap keymaps                       │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: <leader>xa
			vim.keymap.set("n", "<leader>xa", function()
				ts_swap.swap_next("@parameter.inner")
			end, { desc = "Swap current arg with the next arg." })
			-- KEYMAP: <leader>xc
			vim.keymap.set("n", "<leader>xc", function()
				ts_swap.swap_next("@class.outer")
			end, { desc = "Swap current class with the next class." })
			-- KEYMAP: <leader>xf
			vim.keymap.set("n", "<leader>xf", function()
				ts_swap.swap_next("@function.outer")
			end, { desc = "Swap current function with the next function." })
			-- KEYMAP: <leader>xA
			vim.keymap.set("n", "<leader>xA", function()
				ts_swap.swap_previous("@parameter.inner")
			end, { desc = "Swap current arg with the previous arg." })
			-- KEYMAP: <leader>xC
			vim.keymap.set("n", "<leader>xC", function()
				ts_swap.swap_previous("@class.outer")
			end, { desc = "Swap current class with the previous class." })
			-- KEYMAP: <leader>xF
			vim.keymap.set("n", "<leader>xF", function()
				ts_swap.swap_previous("@function.outer")
			end, { desc = "Swap current function with the previous function." })

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                  Repeatable move keymaps                 │
			-- ╰─────────────────────────────────────────────────────────╯
			-- KEYMAP: }
			vim.keymap.set(
				{ "n", "x", "o" },
				"}",
				ts_repeat_move.repeat_last_move_next,
				{ desc = "Repeat last supported motion (remap of ';')" }
			)
			-- KEYMAP: {
			vim.keymap.set(
				{ "n", "x", "o" },
				"{",
				ts_repeat_move.repeat_last_move_previous,
				{ desc = "Repeat last supported motion in opposite direction (remap of ',')" }
			)
			-- Make builtin f, F, t, T also repeatable with } and {.
			vim.keymap.set({ "n", "x", "o" }, "f", ts_repeat_move.builtin_f_expr, { expr = true })
			vim.keymap.set({ "n", "x", "o" }, "F", ts_repeat_move.builtin_F_expr, { expr = true })
			vim.keymap.set({ "n", "x", "o" }, "t", ts_repeat_move.builtin_t_expr, { expr = true })
			vim.keymap.set({ "n", "x", "o" }, "T", ts_repeat_move.builtin_T_expr, { expr = true })
		end,
	},
}
