-- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

---------- OPTIONS + VARIABLES
-- Set Options
vim.opt.number = true
vim.opt.relativenumber = true

-- Global Editor Variables
vim.g.mapleader = ","

---------- MAPPINGS
-- Allow semilcolon (;) to be treated the same as colon (:).
vim.keymap.set({'n', 'v'}, ';', ':')

-- Maps to save / exit.
vim.keymap.set({'n', 'i'}, '<leader>e', ':x!<cr>')
vim.keymap.set({'n', 'i'}, '<leader>E', ':xa!<cr>')
vim.keymap.set({'n', 'i'}, '<leader>s', ':update<cr>')
