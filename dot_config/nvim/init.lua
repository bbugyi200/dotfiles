-- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- TODO: Configure UltiSnips
-- TODO: Configure LSP.
-- TODO: Install neovim only plugins you wanted to try.
-- TODO: Add support for neovim to zorg.
-- TODO: Fix all 'v*' shell functions so they support neovim.
-- TODO: Replace NerdTree?
-- TODO: Add maps that delete buffers (ex: ,dd)
-- TODO: Split vim options out to separate *.lua file.
-- TODO: Split vim maps out to separate *.lua file.

-- <Leader> and <LocalLeader> need to be configured BEFORE loading lazy.nvim.
vim.g.mapleader = ","
vim.g.maplocalleader = "\\"


---------- VIM COMMANDS
vim.cmd([[
  colorscheme desert
]])


---------- VIM OPTIONS
-- Use spaces instead of tabs.
vim.opt.expandtab = true
vim.opt.shiftwidth = 0
vim.opt.tabstop = 2

-- Configure relative numbered lines.
vim.opt.number = true
vim.opt.relativenumber = true

-- Configure 'undo' functionality.
vim.opt.undodir = "~/.vim/undo"
vim.opt.undofile = true


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

-- Map to navigate to alternate file.
vim.keymap.set('n', '<C-\\>', '<C-^>')

-- Visual map to go to end-of-line.
vim.keymap.set('v', '<space>', '$<left>')


---------- LOAD OTHER MODULES
require("config.lazy")
