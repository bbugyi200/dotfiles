--- Miscellanous VimScript plugins live here.
--
-- P2: Install https://github.com/lervag/vimtex ?!
-- P2: Install https://github.com/mrcjkb/rustaceanvim ?!
-- P2: Review https://nvimluau.dev/ for plugins to install!
-- P2: Install one of the following colorscheme plugins?:
--     * https://github.com/mhartington/oceanic-next colorscheme
--     * Install https://github.com/folke/tokyonight.nvim instead
-- P2: Install https://github.com/otavioschwanck/arrow.nvim ?
-- P3: Install https://github.com/mrjones2014/legendary.nvim ?
-- P3: Install https://github.com/sudormrfbin/cheatsheet.nvim ?
-- P3: Install https://github.com/mhinz/neovim-remote ?

return {
	-- PLUGIN: http://github.com/dylon/vim-antlr (for syntax highlighting of *.g4 files)
	{ "dylon/vim-antlr", ft = "antlr4" },
	-- PLUGIN: http://github.com/godlygeek/tabular
	{ "godlygeek/tabular", cmd = "Tabularize" },
	-- PLUGIN: http://github.com/google/vim-searchindex
	{ "google/vim-searchindex", event = "VeryLazy" },
	-- PLUGIN: http://github.com/jamessan/vim-gnupg
	{ "jamessan/vim-gnupg", event = "VeryLazy" },
	-- PLUGIN: http://github.com/mityu/vim-applescript
	{ "mityu/vim-applescript", ft = "applescript" },
	-- PLUGIN: http://github.com/wellle/targets.vim
	{ "wellle/targets.vim", event = "VeryLazy" },
}
