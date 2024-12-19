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
