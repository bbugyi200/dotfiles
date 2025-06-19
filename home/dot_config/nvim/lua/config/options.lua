-- P2: Add OPTION comment to explain the purpose of each option!
-- P2: Set 'infercase' to fix completion for capital words?
-- P3: Add an alternative 'spellfile' for specialist jargon?
-- P3: Add `:set spelllang=en_us` to `vim.opt.spelllang` to enable American English words only?

local vo = vim.opt

-- Use spaces instead of tabs.
vo.expandtab = true
vo.shiftwidth = 2
vo.tabstop = 2

-- Configure relative numbered lines.
vo.number = true
vo.relativenumber = true

-- Configure 'undo' functionality.
vo.undofile = true

-- Configure LSP options
vo.omnifunc = "v:lua.vim.lsp.omnifunc"
vo.formatexpr = "v:lua.vim.lsp.formatexpr"
vo.tagfunc = "v:lua.vim.lsp.tagfunc"

-- Case-insensitive search by default
vo.ignorecase = true
vo.smartcase = true

-- Configure system clipboard
if vim.fn.has("clipboard") == 1 then
	if vim.fn.has("unnamedplus") == 1 then
		vo.clipboard = "unnamed,unnamedplus"
	else
		vo.clipboard = "unnamed"
	end
end

-- Enables 24-bit RGB color in the TUI.
vo.termguicolors = true

-- Configure completeopt / wildmenu / wildmenu for better command-line completion.
vo.completeopt = { "menu", "menuone", "noselect" }
vo.wildmenu = true
vo.wildmode = { "longest:full", "full" }

-- Allow incrementing / decrementing letters with CTRL-A / CTRL-X.
vo.nrformats = { "alpha", "bin", "hex" }

-- Configure 'infercase' to fix completion for capital words.
vo.infercase = true

-- Highlight cursor line and line number.
vo.cursorline = true

-- Disable line-wrapping.
vo.wrap = false
