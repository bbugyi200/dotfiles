-- The Lua code in this file is loaded BEFORE any other NeoVim configuration has been loaded.

-- Set <leader> and <localleader> keys.
vim.g.mapleader = ","
vim.g.maplocalleader = "\\"

-- Set the Python 3 host program for Neovim. This is necessary in cases where I
-- am unable to run `pip install pynvim` in the system Python 3 environment.
local pyenv_python_bin = vim.env.HOME .. "/.pyenv/versions/neovim/bin/python"
if vim.fn.filereadable(pyenv_python_bin) then
	vim.g.python3_host_prog = pyenv_python_bin
end
