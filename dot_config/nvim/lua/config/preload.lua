-- The Lua code in this file is loaded BEFORE any other NeoVim configuration has been loaded.

vim.g.mapleader = ","
vim.g.maplocalleader = "\\"
vim.cmd([[
  colorscheme desert
]])

-- Disable netrw at the beginning of init.lua to let nvim-tree handle file browsing.
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1
