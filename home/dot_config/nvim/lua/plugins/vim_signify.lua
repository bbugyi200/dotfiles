return {
	-- PLUGIN: http://github.com/mhinz/vim-signify
	-- TROUBLESHOOTING:
	-- If signs look stale in a clean repo, run :SignifyDebug first. A common root cause is VCS
	-- command failure (e.g., "fatal: multi-pack-index version 2 not recognized" from git diff/status).
	-- Fix by backing up/removing .git/objects/pack/multi-pack-index, then refresh signs.
	{
		"mhinz/vim-signify",
		dependencies = {
			-- For repeatable motions using { and }.
			"nvim-treesitter/nvim-treesitter-textobjects",
		},
		init = function()
			local repeat_move = require("bb_utils").require_repeatable_move()
			local bb = require("bb_utils")

			vim.opt.signcolumn = "yes"
			vim.g.signify_skip_filename_pattern = { "\\.pipertmp.*" }

			-- Customize Sign Colors
			vim.cmd([[
        highlight SignifySignAdd    ctermfg=green  guifg=#00ff00 cterm=NONE gui=NONE
        highlight SignifySignDelete ctermfg=red    guifg=#ff0000 cterm=NONE gui=NONE
        highlight SignifySignChange ctermfg=yellow guifg=#ffff00 cterm=NONE gui=NONE
      ]])

			-- ╭─────────────────────────────────────────────────────────╮
			-- │                         KEYMAPS                         │
			-- ╰─────────────────────────────────────────────────────────╯
			local move_hunk = repeat_move.make_repeatable_move(function(opts)
				if opts.forward then
					bb.feedkeys("<Plug>(signify-next-hunk)")
				else
					bb.feedkeys("<Plug>(signify-prev-hunk)")
				end
			end)

			-- KEYMAP: [h
			vim.keymap.set("n", "[h", function()
				move_hunk({ forward = false })
			end, { desc = "Jump to previous hunk." })

			-- KEYMAP: ]h
			vim.keymap.set("n", "]h", function()
				move_hunk({ forward = true })
			end, { desc = "Jump to next hunk." })
		end,
	},
}
