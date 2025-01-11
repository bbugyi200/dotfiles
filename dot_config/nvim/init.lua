--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- Configuration that needs to be loaded FIRST (e.g. to set mapleader).
require("config.preload")
-- Configure settings / options that are NOT specific to a plugin.
require("config.options")
-- Configure keymaps that are NOT specific to a plugin.
require("config.keymaps")
-- Configure autocmds that are NOT specific to a plugin.
require("config.autocmds")
-- Configure lazy.nvim and ALL installed plugins!
require("config.lazy")
-- Configure LSP (and cmp.nvim ATTOW, but this should be split out to cmp.lua soon)
require("config.lsp")
-- Configuration that needs to be loaded LAST.
require("config.postload")

-- =============== TODO SOON ===============
-- TODO[ ]: Add `gV` map!
-- TODO[ ]: Install ALL plugins listed in go/neovim!
-- TODO[ ]: Use different keymap (NOT <cr>) for accepting completion!
-- TODO[ ]: Improve local vimrc
--       * [ ] Add autocmd for $(pwd)/.vimrc.local
--       * [ ] Move ~/.vimrc.local to ~/etc/vimrc?
-- TODO[ ]: Configure http://go/analysislsp-neovim !
-- TODO[ ]: Configure cmp-buganizer and cmp-googlers! See http://go/neovim.
-- TODO[ ]: Configure all internal plugins mentioned in http://go/neovim !
-- TODO[ ]: Telescope extensions
--       * [ ] Install lots of Telescope extensions!
--       * [ ] Use ,t<L> maps with Telescope builtins and extensions!
--       * [ ] Find alternative to `:Telescope buffers` that favors most recent buffers.
-- TODO[ ]: Fix '-', '|', and '_' maps to default to lowest buffer num (NOT 1).
-- TODO[ ]: Install https://github.com/stevearc/conform.nvim for code formatting!

-- =============== TODO LATER ===============
-- TODO[ ]: Add neocitc integrations described by https://team.git.corp.google.com/neovim-dev/neocitc/+/refs/heads/main
-- TODO[ ]: Write install/update script for building/installing NeoVim from source!
--          (CMD: make CMAKE_BUILD_TYPE=RelWithDebInfo -j && sudo make CMAKE=/opt/homebrew/bin/cmake install)
-- TODO[ ]: Move glug.lua to funcs/glug.lua?
-- TODO[ ]: Install https://github.com/sudormrfbin/cheatsheet.nvim ?
-- TODO[ ]: Install "vim-scripts/vcscommand.vim" with vcscommand-g4 as dep?
-- TODO[ ]: Add markdown LSP support!
-- TODO[ ]: Add fugitive keymaps!
-- TODO[ ]: Use tree splitter text objects (ex: cif keymap to clear and edit a function body)
-- TODO[ ]: Create `vchez` script!
-- TODO[ ]: Add on-the-fly luasnip snippet for TODOs in this file!
-- TODO[ ]: Make bufferline buffers use less space!
-- TODO[ ]: Install neovim only plugins you wanted to try.
--       * [ ] https://github.com/mfussenegger/nvim-dap
-- TODO[ ]: Improve https://github.com/akinsho/bufferline.nvim!
--       * [ ] Group buffers by extension
--       * [ ] Add :BufferLinePick map for splits and tabs!
--       * [ ] Use :BufferLineCycleNext for ]b!
--       * [ ] Add mappings to close all buffers, left buffers, and right buffers!
--       * [ ] Use ordinal numbers instead of buffer numbers?
--       * [ ] Figure out how to get diagnostics WITHOUT breaking highlighting!
-- TODO[ ]: Install https://github.com/zbirenbaum/copilot-cmp!
-- TODO[ ]: Test nvim built-in terminal support!
-- TODO[ ]: Install more completion sources
--          (see https://github.com/hrsh7th/nvim-cmp/wiki/List-of-sources)!:
--       * [ ] https://github.com/KadoBOT/cmp-plugins
--       * [ ] https://github.com/zbirenbaum/copilot-cmp
--       * [ ] https://github.com/garyhurtz/cmp_kitty
--       * [ ] https://github.com/andersevenrud/cmp-tmux
-- TODO[ ]: Split lsp.lua!
--       * [ ] lspconfig.lua
--       * [ ] cmp.lua
-- TODO[ ]: Configure Lua-Snips
--       * [X] Migrate all useful 'all' snippets.
--       * [ ] Add snippets for lua (ex: if, elif, ife, funcs, snippets, todo).
--       * [ ] Migrate all useful Dart snippets.
--       * [ ] Migrate all useful Java snippets.
--       * [ ] Migrate all useful Python snippets.
--       * [ ] Migrate all useful shell snippets.
--       * [ ] Migrate all useful zorg snippets.
--       * [ ] Create snippet that replaces `hc`!
-- TODO[ ]: Walk through vimrc line by line.
-- TODO[ ]: Walk through plugins.vim line by line.
-- TODO[ ]: Implement y* maps that copy parts of filename.
-- TODO[ ]: Merge config.luasnip into plugin.luasnip?
-- TODO[ ]: Configure clangd LSP server for work!
-- TODO[ ]: Get line/column number on bottom buffer tab back (with lualine?).
