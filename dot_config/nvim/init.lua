--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- TODO[X]: Auto-run `chezmoi apply` on-save!
-- TODO[X]: Auto-run `stylua` on save!
-- TODO[X]: Fix <Tab> key so it is used ONLY for snippet expansion.
-- TODO[X]: Add keymap to switch luasnip choices!
-- TODO[X]: Add autocmd for ~/.local/share/chezmoi/dot_config/nvim/snippets/*.lua
-- TODO[X]: Fix case-sensitive search (default: smart)
-- TODO[X]: Fix clipboard
-- TODO[X]: Add key map to search for <WORD>.
-- TODO[X]: Fix ,s key map in INSERT mode.
-- TODO[X]: Add maps that delete buffers (ex: ,dd)
-- TODO[X]: Fix undo file (stop using vim undofile)
-- TODO[ ]: Install session-persistance plugin!
--          (see https://claude.ai/chat/0a8a7904-72d0-4624-813d-a62e7d1ff0c7)
-- TODO[ ]: Install more completion sources
--          (see https://github.com/hrsh7th/nvim-cmp/wiki/List-of-sources)!:
--       * [ ] https://github.com/L3MON4D3/cmp-luasnip-choice
--       * [ ] https://github.com/KadoBOT/cmp-plugins
--       * [ ] https://github.com/zbirenbaum/copilot-cmp
--       * [ ] https://github.com/garyhurtz/cmp_kitty
--       * [ ] https://github.com/andersevenrud/cmp-tmux
-- TODO[ ]: Split lsp.lua into 3 files!
-- TODO[ ]: Get .vimrc.local working on cloudtop.
-- TODO[ ]: Add support for neovim to zorg.
-- TODO[ ]: Fix all 'v*' shell functions so they support neovim.
-- TODO[ ]: Create `vchez` script!
-- TODO[ ]: Configure language server(s) for personal work.
--       * [X] Lua
--       * [ ] Python
--       * [ ] Shell
--       * [ ] Rust
-- TODO[ ]: Configure Lua-Snips
--       * [X] Migrate all useful 'all' snippets.
--       * [ ] Add snippets for lua (ex: if, elif, ife, funcs, snippets, todo).
--       * [ ] Migrate all useful Dart snippets.
--       * [ ] Migrate all useful Java snippets.
--       * [ ] Migrate all useful Python snippets.
--       * [ ] Migrate all useful shell snippets.
--       * [ ] Migrate all useful zorg snippets.
--       * [ ] Get local snippets working!
--       * [ ] Create snippet that replaces `hc`!
-- TODO[ ]: Migrate from fzf-lua to telescope?
-- TODO[ ]: Migrate to https://github.com/akinsho/bufferline.nvim!
-- TODO[ ]: Walk through vimrc line by line.
-- TODO[ ]: Walk through plugins.vim line by line.
-- TODO[ ]: Add plugin for git/fig diffs in sidebar.
-- TODO[ ]: Install neovim only plugins you wanted to try.
--       * [ ] https://github.com/mfussenegger/nvim-dap
-- TODO[ ]: Replace NerdTree?
-- TODO[ ]: Implement y* maps that copy parts of filename.
-- TODO[ ]: Get line/column number on bottom buffer tab back.
-- TODO[ ]: Merge config.luasnip into plugin.luasnip?
-- TODO[ ]: Configure clangd LSP server for work!
-- TODO[ ]: Test nvim built-in terminal support!
-- TODO[ ]: Install https://github.com/zbirenbaum/copilot-cmp!

vim.g.mapleader = ","
vim.g.maplocalleader = "\\"
vim.cmd([[
  colorscheme desert
]])

require("config.options")
require("config.keymaps")
require("config.autocmds")
require("config.lazy")
require("config.lsp")
require("config.trouble")
require("config.luasnip")
