--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- TODO: Configure Lua-Snips
--       * [X] Migrate all useful 'all' snippets.
--       * [ ] Add snippets for lua (ex: if, elif, ife, funcs, snippets, todo).
--       * [ ] Migrate all useful Dart snippets.
--       * [ ] Migrate all useful Java snippets.
--       * [ ] Migrate all useful Python snippets.
--       * [ ] Migrate all useful shell snippets.
--       * [ ] Migrate all useful zorg snippets.
--       * [ ] Get local snippets working!
-- TODO: Reload lua files:
--       * [ ] Auto-reload on file changes.
--       * [ ] Add map that reloads all lua files (including snippets)
-- TODO: Migrate to https://github.com/akinsho/bufferline.nvim!
-- TODO: Walk through vimrc line by line.
-- TODO: Walk through plugins.vim line by line.
-- TODO: Add plugin for git/fig diffs in sidebar.
-- TODO: Install neovim only plugins you wanted to try.
-- TODO: Add support for neovim to zorg.
-- TODO: Fix all 'v*' shell functions so they support neovim.
-- TODO: Replace NerdTree?
-- TODO: Add maps that delete buffers (ex: ,dd)
-- TODO: Get .vimrc.local working on cloudtop.
-- TODO: Configure language server(s) for personal work.
-- TODO: Fix case-sensitive search (default: smart)
-- TODO: Auto-run `stylua` on save!
-- TODO: Implement y* maps that copy parts of filename.
-- TODO: Get line/column number on bottom buffer tab back.
-- TODO: Add key maps for FzfLua to open in splits.
-- TODO: Add key map to search for <WORD>.
-- TODO: Fix ,s key map in INSERT mode.

vim.g.mapleader = ","
vim.g.maplocalleader = "\\"
vim.cmd([[
  colorscheme desert
]])

require("config.options")
require("config.keymaps")
require("config.lazy")
require("config.lsp")
require("config.trouble")
require("config.luasnip")
