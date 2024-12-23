--- My (http://github.com/bbugyi200) Lua Configuration for NeoVim.

-- TODO[X]: Auto-run `chezmoi apply` on-save!
-- TODO[X]: Auto-run `stylua` on save!
-- TODO[ ]: Fix <Tab> key so it is used ONLY for snippet expansion.
-- TODO[ ]: Add keymap to switch luasnip choices!
-- TODO[ ]: Reload snippet files!
--       * [ ] Add mapping to reload snippets manually
--       * [ ] Enable libuv file watching?
-- TODO[ ]: Split lsp.lua into 3 files!
-- TODO[ ]: Install session-persistance plugin!
-- TODO[ ]: Fix case-sensitive search (default: smart)
-- TODO[ ]: Fix clipboard
-- TODO[ ]: Add key map to search for <WORD>.
-- TODO[ ]: Fix ,s key map in INSERT mode.
-- TODO[ ]: Add maps that delete buffers (ex: ,dd)
-- TODO[ ]: Get .vimrc.local working on cloudtop.
-- TODO[ ]: Add support for neovim to zorg.
-- TODO[ ]: Fix all 'v*' shell functions so they support neovim.
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
-- TODO[ ]: Replace NerdTree?
-- TODO[ ]: Implement y* maps that copy parts of filename.
-- TODO[ ]: Get line/column number on bottom buffer tab back.
-- TODO[ ]: Merge config.luasnip into plugin.luasnip?
-- TODO[ ]: Configure clangd LSP server for work!
-- TODO[ ]: Test nvim built-in terminal support!

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
