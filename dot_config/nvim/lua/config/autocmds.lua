-- P0: Add all of my 'autocmds' to the same group to support `:Telescope autocmd`?!
-- P0: Add keymaps to 'qf' windows to quit (q) and use Trouble (Q)!
-- P2: Prefix every autocmd in this file with an AUTOCMD comment!
local kill_buffer = require("util.kill_buffer").kill_buffer

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

--- Quits a "fake buffer" (e.g. a help window or quickfix window).
local function quit_fake_buffer()
	kill_buffer("#")
	if #vim.api.nvim_list_wins() > 1 then
		vim.cmd("wincmd c")
	end
end

-- Configure LSP autocmds
vim.api.nvim_command("augroup LSP")
vim.api.nvim_command("autocmd!")
vim.api.nvim_command("autocmd CursorHold  <buffer> lua vim.lsp.buf.document_highlight()")
vim.api.nvim_command("autocmd CursorHoldI <buffer> lua vim.lsp.buf.document_highlight()")
vim.api.nvim_command("autocmd CursorMoved <buffer> lua vim.lsp.util.buf_clear_references()")
vim.api.nvim_command("augroup END")

-- Automatic `chezmoi apply` when chezmoi files are changed.
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

-- Automatic luasnippet reloads for chezmoi snippet files.
local chez_snippet_dir = chezmoi_dir .. "/dot_config/nvim/luasnippets"
local snippet_dir = os.getenv("HOME") .. "/.config/nvim/luasnippets"
vim.api.nvim_create_autocmd("BufWritePost", {
	pattern = { chez_snippet_dir .. "/*" },
	callback = function()
		require("luasnip.loaders").reload_file(snippet_dir .. "/" .. vim.fn.expand("%:t"))
	end,
	desc = "Reload luasnip snippet files when they are modified in chezmoi dir.",
})

-- Automatic mkdir for parent dirs of new files.
vim.api.nvim_create_autocmd("BufWritePre", {
	group = vim.api.nvim_create_augroup("BWCCreateDir", { clear = true }),
	callback = function()
		create_dir(vim.fn.expand("<afile>"), assert(tonumber(vim.fn.expand("<abuf>"))))
	end,
})

-- Automatically resize windows when vim is resized.
vim.api.nvim_create_autocmd("VimResized", {
	pattern = "*",
	command = "wincmd =",
	group = vim.api.nvim_create_augroup("window_resize", {}),
})

-- Add 'q', 'Q', and 'H' keymaps to vimdoc :help windows.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "help" },
	callback = function()
		-- KEYMAP: q
		vim.keymap.set("n", "q", quit_fake_buffer, { buffer = true, desc = "Close the current :help window." })
		-- KEYMAP: Q
		vim.keymap.set(
			"n",
			"Q",
			"<cmd>wincmd o<cr>",
			{ buffer = true, desc = "Close all windows BUT the :help window." }
		)
		-- KEYMAP: H
		vim.keymap.set("n", "H", "<cmd>Telescope heading<cr>", { desc = "Telescope heading" })
	end,
})

-- Add 'q' and 'Q' keymaps to quickfix :help windows.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "qf" },
	callback = function()
		-- KEYMAP: q
		vim.keymap.set("n", "q", quit_fake_buffer, { buffer = true, desc = "Close the current quickfix window." })
		-- KEYMAP: Q
		vim.keymap.set(
			"n",
			"Q",
			"<cmd>cclose<cr><cmd>Trouble quickfix<cr>",
			{ buffer = true, desc = "Send the quickfix results to Trouble." }
		)
	end,
})
