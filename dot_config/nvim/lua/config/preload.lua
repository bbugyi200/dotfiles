-- The Lua code in this file is loaded BEFORE any other NeoVim configuration has been loaded.

-- Set <leader> and <localleader> keys.
vim.g.mapleader = ","
vim.g.maplocalleader = "\\"

-- Set the colorscheme.
vim.cmd([[
  colorscheme desert
]])

-- Disable netrw at the beginning of init.lua to let nvim-tree handle file browsing.
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1
