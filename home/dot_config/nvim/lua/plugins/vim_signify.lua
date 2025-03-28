return {
	-- PLUGIN: http://github.com/mhinz/vim-signify
	{
		"mhinz/vim-signify",
		dependencies = {
			-- For repeatable motions using [[ and ]].
			"nvim-treesitter/nvim-treesitter-textobjects",
		},
		init = function()
			local ts_repeat_move = require("nvim-treesitter.textobjects.repeatable_move")
			local feedkeys = require("util.feedkeys")

			vim.opt.signcolumn = "yes"
			vim.g.signify_skip_filename_pattern = { "\\.pipertmp.*" }

			local next_hunk, prev_hunk = ts_repeat_move.make_repeatable_move_pair(function()
				feedkeys("<Plug>(signify-next-hunk)")
			end, function()
				feedkeys("<Plug>(signify-prev-hunk)")
			end)

			-- KEYMAP(N): [h
			vim.keymap.set("n", "[h", next_hunk, { desc = "Jump to previous hunk." })

			-- KEYMAP(N): ]h
			vim.keymap.set("n", "]h", prev_hunk, { desc = "Jump to next hunk." })

			-- Customize Sign Colors
			vim.cmd([[
        highlight SignifySignAdd    ctermfg=green  guifg=#00ff00 cterm=NONE gui=NONE
        highlight SignifySignDelete ctermfg=red    guifg=#ff0000 cterm=NONE gui=NONE
        highlight SignifySignChange ctermfg=yellow guifg=#ffff00 cterm=NONE gui=NONE
      ]])
		end,
	},
}
