-- P2: Add OPTION comment to explain the purpose of each option!
-- P2: Set 'infercase' to fix completion for capital words?
-- P3: Add an alternative 'spellfile' for specialist jargon?
-- P3: Add `:set spelllang=en_us` to `vim.opt.spelllang` to enable American English words only?

-- Use spaces instead of tabs.
vim.opt.expandtab = true
vim.opt.shiftwidth = 2
vim.opt.tabstop = 2

-- Configure relative numbered lines.
vim.opt.number = true
vim.opt.relativenumber = true

-- Configure 'undo' functionality.
vim.opt.undofile = true

-- Configure LSP options
vim.opt.omnifunc = "v:lua.vim.lsp.omnifunc"
vim.opt.formatexpr = "v:lua.vim.lsp.formatexpr"
vim.opt.tagfunc = "v:lua.vim.lsp.tagfunc"

-- Case-insensitive search by default
vim.opt.ignorecase = true
vim.opt.smartcase = true

-- Configure system clipboard
if vim.fn.has("clipboard") == 1 then
	if vim.fn.has("unnamedplus") == 1 then
		vim.opt.clipboard = "unnamed,unnamedplus"
	else
		vim.opt.clipboard = "unnamed"
	end
end

-- Enables 24-bit RGB color in the TUI.
vim.opt.termguicolors = true

-- Configure completeopt / wildmenu / wildmenu for better command-line completion.
vim.opt.completeopt = { "menu", "menuone", "noselect" }
vim.opt.wildmenu = true
vim.opt.wildmode = { "longest:full", "full" }

-- Allow incrementing / decrementing letters with CTRL-A / CTRL-X.
vim.opt.nrformats = { "alpha", "bin", "hex" }

-- Configure 'infercase' to fix completion for capital words.
vim.opt.infercase = true

-- Highlight cursor line and line number.
vim.opt.cursorline = true
