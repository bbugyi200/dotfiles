--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- =============== NOW ===============
-- TODO[ ]: Configure language server(s) for personal work.
--       * [X] Lua
--       * [ ] Python
--       * [ ] Shell
--       * [ ] Rust
-- TODO[ ]: Migrate from fzf-lua to telescope!
-- TODO[ ]: Add support for neovim to zorg.
-- TODO[ ]: Get .vimrc.local working on cloudtop.
-- TODO[ ]: Fix all 'v*' shell functions so they support neovim.
-- TODO[ ]: Create `vchez` script!
-- TODO[ ]: Fix NVimTree map so it uses CWD.
-- TODO[ ]: Add [w and ]w maps!
-- TODO[ ]: Fix '-', '|', and '_' maps to default to lowest buffer num (NOT 1).
--
-- =============== LATER ===============
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
--       * [ ] Get local snippets working!
--       * [ ] Create snippet that replaces `hc`!
-- TODO[ ]: Walk through vimrc line by line.
-- TODO[ ]: Walk through plugins.vim line by line.
-- TODO[ ]: Add plugin for git/fig diffs in sidebar.
-- TODO[ ]: Implement y* maps that copy parts of filename.
-- TODO[ ]: Merge config.luasnip into plugin.luasnip?
-- TODO[ ]: Configure clangd LSP server for work!
-- TODO[ ]: Get line/column number on bottom buffer tab back (with lualine?).

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
