-- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- <Leader> and <LocalLeader> need to be configured BEFORE loading lazy.nvim.
vim.g.mapleader = ","
vim.g.maplocalleader = "\\"


---------- VIM COMMANDS + OPTIONS
-- Vim Commands
vim.cmd([[
  colorscheme desert
]])
-- Set Options
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.undofile = true
vim.opt.undodir = "~/.vim/undo"


---------- MAPPINGS
-- Allow semilcolon (;) to be treated the same as colon (:).
vim.keymap.set({'n', 'v'}, ';', ':')

-- Maps to save / exit.
vim.keymap.set({'n', 'i'}, '<leader>e', ':x!<cr>')
vim.keymap.set({'n', 'i'}, '<leader>E', ':xa!<cr>')
vim.keymap.set({'n', 'i'}, '<leader>s', ':update<cr>')

-- Maps that make buffer navigation easier.
vim.keymap.set('n', '_', ':<C-u>execute "sbuffer " . v:count1<CR>')
vim.keymap.set('n', '|', ':<C-u>execute "vert sbuffer " . v:count1<CR>')
vim.keymap.set('n', '+', ':<C-u>execute "tab sbuffer " . v:count<CR>')
vim.keymap.set('n', '-', ':<C-u>execute "buffer " . v:count1<CR>')


---------- LOAD AND CONFIGURE PLUGINS
require("config.lazy")
