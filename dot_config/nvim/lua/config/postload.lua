-- The Lua code in this file is loaded AFTER all other NeoVim configuration has been loaded.

require("funcs").source_if_exists(vim.env.HOME .. "/.vimrc.local")
