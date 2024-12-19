-- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- <Leader> needs to be configured BEFORE loading lazy.nvim.
vim.g.mapleader = ","
require("config.lazy")

---------- VIM COMMANDS + OPTIONS
-- Vim 'set ...' Commands
vim.cmd([[
  colorscheme desert
]])
-- Set Options
vim.opt.number = true
vim.opt.relativenumber = true

---------- MAPPINGS
-- <Leader> needs to be configured again for some reason...
vim.g.mapleader = ","

-- Allow semilcolon (;) to be treated the same as colon (:).
vim.keymap.set({'n', 'v'}, ';', ':')

-- Maps to save / exit.
vim.keymap.set({'n', 'i'}, '<Leader>e', ':x!<CR>')
vim.keymap.set({'n', 'i'}, '<Leader>E', ':xa!<CR>')
vim.keymap.set({'n', 'i'}, '<Leader>s', ':update<CR>')
