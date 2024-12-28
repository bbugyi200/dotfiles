--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- =============== NOW ===============
-- TODO[X]: Add support for neovim to zorg.
-- TODO[X]: Fix zorq.vim syntax file
-- TODO[ ]: Better Snippets
--       * [ ] Add '@WIP' zorg snippet
--       * [ ] Add 'z' zorg snippet
--       * [ ] Add 'o0-9' zorg snippet
--       * [ ] Add bullet zorg snippets (ex: NOTES)
--       * [ ] Add '#1-4' header zorg snippets
--       * [ ] Add another choice to 's' lua snippet.
--       * [ ] Add 'dt' snippet (same as 'dt0')
--       * [ ] Add 'hm' snippet (same as 'hm0')
-- TODO[ ]: Support local snippets!
--       * [ ] Add support for zorg snippets!
--       * [ ] Change directory name from 'snippets' to 'luasnippets'!
--       * [ ] Lazy load local snippets / luasnippets directories!
-- TODO[ ]: Get .vimrc.local working on cloudtop.
-- TODO[ ]: Fix all 'v*' shell functions so they support neovim.
-- TODO[ ]: Fix `:Telescope buffers` to favor most recent buffers.
--
-- =============== LATER ===============
-- TODO[ ]: Use tree splitter text objects (ex: cif keymap to clear and edit a function body)
-- TODO[ ]: Telescope extensions
--       * [ ] Install lots of Telescope extensions!
--       * [ ] Use ,t<L> maps with Telescope builtins and extensions!
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
-- TODO[ ]: Split lsp.lua into 3 files!
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
-- TODO[ ]: Fix '-', '|', and '_' maps to default to lowest buffer num (NOT 1).

vim.g.mapleader = ","
vim.g.maplocalleader = "\\"
vim.cmd([[
  colorscheme desert
]])

require("config.options")
require("config.keymaps")
require("config.autocmds")
require("config.lazy")
require("config.lsp")
require("config.trouble")
require("config.luasnip")
