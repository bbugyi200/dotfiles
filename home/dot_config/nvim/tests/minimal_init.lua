local script_path = debug.getinfo(1, "S").source:sub(2)
local nvim_config_root = vim.fn.fnamemodify(script_path, ":p:h:h")

vim.opt.runtimepath:prepend(nvim_config_root)
vim.opt.swapfile = false
vim.g.mapleader = " "
vim.g.maplocalleader = "\\"
