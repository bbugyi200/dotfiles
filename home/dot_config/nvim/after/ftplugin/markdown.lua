--- Filetype: markdown

vim.bo.textwidth = 120
vim.wo.spell = true

require("config.bob_pomodoro_keymaps").setup_buffer(0)
require("config.bob_keymaps").setup_buffer(0)
