--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- TODO: Configure UltiSnips
-- TODO: Configure LSP.
-- TODO: Install neovim only plugins you wanted to try.
-- TODO: Add support for neovim to zorg.
-- TODO: Fix all 'v*' shell functions so they support neovim.
-- TODO: Replace NerdTree?
-- TODO: Add maps that delete buffers (ex: ,dd)
-- TODO: Split vim options out to separate *.lua file.
-- TODO: Split vim maps out to separate *.lua file.
-- TODO: Add <space> map that searches current buffer filenames.

vim.g.mapleader = ","
vim.g.maplocalleader = "\\"

vim.cmd([[
  colorscheme desert
]])

require("config.options")
require("config.keymaps")
require("config.lazy")
