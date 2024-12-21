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

-- Configure LSP options
vim.opt.omnifunc = "v:lua.vim.lsp.omnifunc"
vim.opt.formatexpr = "v:lua.vim.lsp.formatexpr"
vim.opt.tagfunc = "v:lua.vim.lsp.tagfunc"
