-- P2: Add all of my 'autocmds' to the same group to support `:Telescope autocmd`?!

local quit_special_buffer = require("util.quit_special_buffer")

--- Create the parent directory of {file} if it does not already exist.
---
---@param file string The file whose parent directory should be created.
---@param buf number The buffer number of the buffer containing {file}.
local function create_dir(file, buf)
	local buftype = vim.api.nvim_buf_get_option(buf, "buftype")
	if buftype == "" and not file:match("^%w+:/") then
		local dir = vim.fn.fnamemodify(file, ":h")
		if vim.fn.isdirectory(dir) == 0 then
			vim.fn.mkdir(dir, "p")
		end
	end
end

-- AUTOCMD: Configure LSP autocmds
vim.api.nvim_command("augroup LSP")
vim.api.nvim_command("autocmd!")
vim.api.nvim_command("autocmd CursorHold  <buffer> lua vim.lsp.buf.document_highlight()")
vim.api.nvim_command("autocmd CursorHoldI <buffer> lua vim.lsp.buf.document_highlight()")
vim.api.nvim_command("autocmd CursorMoved <buffer> lua vim.lsp.util.buf_clear_references()")
vim.api.nvim_command("augroup END")

-- AUTOCMD: Automatic `chezmoi apply` when chezmoi files are changed.
local chezmoi_dir = os.getenv("HOME") .. "/.local/share/chezmoi"
vim.api.nvim_create_autocmd("BufWritePost", {
	pattern = {
		chezmoi_dir .. "/*",
		"/tmp/chezmoi-edit*",
	},
	command = "silent! !chezmoi apply",
	group = vim.api.nvim_create_augroup("ChezmoiAutoApply", { clear = true }),
	desc = "Apply chezmoi automatically after writing to chezmoi-managed files",
})

-- AUTOCMD: Automatic luasnippet reloads for chezmoi snippet files.
local chez_snippet_dir = chezmoi_dir .. "/home/dot_config/nvim/luasnippets"
local snippet_dir = os.getenv("HOME") .. "/.config/nvim/luasnippets"
vim.api.nvim_create_autocmd("BufWritePost", {
	pattern = { chez_snippet_dir .. "/*" },
	callback = function()
		require("luasnip.loaders").reload_file(snippet_dir .. "/" .. vim.fn.expand("%:t"))
	end,
	desc = "Reload luasnip snippet files when they are modified in chezmoi dir.",
})

-- AUTOCMD: Automatic mkdir for parent dirs of new files.
vim.api.nvim_create_autocmd("BufWritePre", {
	group = vim.api.nvim_create_augroup("BWCCreateDir", { clear = true }),
	callback = function()
		create_dir(vim.fn.expand("<afile>"), assert(tonumber(vim.fn.expand("<abuf>"))))
	end,
})

-- AUTOCMD: Automatically resize windows when vim is resized.
vim.api.nvim_create_autocmd("VimResized", {
	pattern = "*",
	command = "wincmd =",
	group = vim.api.nvim_create_augroup("window_resize", {}),
})

-- AUTOCMD: Configuration that is specific to 'help' buffers.
vim.api.nvim_create_autocmd("BufWinEnter", {
	callback = function()
		-- Abort if the buffer is not a help buffer.
		if vim.bo.buftype ~= "help" then
			return
		end

		-- KEYMAP: q
		vim.keymap.set("n", "q", function()
			quit_special_buffer(true)
		end, {
			buffer = true,
			desc = "Close the help buffer.",
		})
		-- KEYMAP: Q
		vim.keymap.set(
			"n",
			"Q",
			"<cmd>wincmd w | wincmd c<cr>",
			{ buffer = true, desc = "Close all windows BUT the :help window." }
		)

		-- HACK: I'm not sure why 'help' buffers don't respect the global settings,
		-- but they don't :/.
		vim.wo.number = true
		vim.wo.relativenumber = true
	end,
})

-- AUTOCMD: Highlight text after yanking it!
vim.api.nvim_create_autocmd("TextYankPost", {
	pattern = "*",
	callback = function()
		vim.highlight.on_yank({
			higroup = "IncSearch",
			timeout = 200,
			on_visual = true,
		})
	end,
})

-- AUTOCMD: set ft=man
vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
	pattern = "*.man",
	callback = function()
		vim.bo.filetype = "man"
	end,
})
