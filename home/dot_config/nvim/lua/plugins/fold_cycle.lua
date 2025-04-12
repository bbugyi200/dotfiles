--- Provides the ability to cycle open and closed folds and nested folds.

return {
	-- PLUGIN: http://github.com/arecarn/vim-fold-cycle
	{
		"arecarn/vim-fold-cycle",
		init = function()
			vim.cmd([[
        let g:fold_cycle_default_mapping = 0 "disable default mappings
        nmap <Tab> <Plug>(fold-cycle-open)
        nmap <S-Tab> <Plug>(fold-cycle-close)

        " Won't close when max fold is opened
        let g:fold_cycle_toggle_max_open  = 0
        " Won't open when max fold is closed
        let g:fold_cycle_toggle_max_close = 0
      ]])
		end,
	},
}
