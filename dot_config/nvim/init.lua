--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- TODO: Configure Lua-Snips
--       * [ ] Migrate all useful 'all' snippets.
--       * [ ] Migrate all useful Dart snippets.
--       * [ ] Migrate all useful Java snippets.
--       * [ ] Migrate all useful shell snippets.
--       * [ ] Migrate all useful zorg snippets.
--       * [ ] Get local snippets working!
-- TODO: Install neovim only plugins you wanted to try.
-- TODO: Add support for neovim to zorg.
-- TODO: Fix all 'v*' shell functions so they support neovim.
-- TODO: Replace NerdTree?
-- TODO: Add maps that delete buffers (ex: ,dd)
-- TODO: Get .vimrc.local working on cloudtop.
-- TODO: Configure language server(s) for personal work.
-- TODO: Fix case-sensitive search (default: smart)

vim.g.mapleader = ","
vim.g.maplocalleader = "\\"
vim.cmd([[
  colorscheme desert
]])

require("config.options")
require("config.keymaps")
require("config.lazy")
require("config.lsp")
require("config.diagnostics")
