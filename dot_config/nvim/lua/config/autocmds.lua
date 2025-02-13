-- P2: Add all of my 'autocmds' to the same group to support `:Telescope autocmd`?!
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
local function quit_special_buffer()
	kill_buffer("#")
	if #vim.api.nvim_list_wins() > 1 then
		vim.cmd("wincmd c")
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
local chez_snippet_dir = chezmoi_dir .. "/dot_config/nvim/luasnippets"
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

-- AUTOCMD: Add 'Q' keymap to vimdoc :help windows.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "help" },
	callback = function()
		-- KEYMAP(N): Q
		vim.keymap.set(
			"n",
			"Q",
			"<cmd>wincmd o<cr>",
			{ buffer = true, desc = "Close all windows BUT the :help window." }
		)
	end,
})

-- AUTOCMD: Add 'Q' keymap to quickfix windows.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "qf" },
	callback = function()
		-- KEYMAP(N): Q
		vim.keymap.set(
			"n",
			"Q",
			"<cmd>cclose<cr><cmd>Trouble quickfix<cr>",
			{ buffer = true, desc = "Send the quickfix results to Trouble." }
		)
	end,
})

-- AUTOCMD: Add 'q' keymap to special buffers.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "help", "qf" },
	callback = function()
		-- KEYMAP(N): q
		vim.keymap.set("n", "q", quit_special_buffer, { buffer = true, desc = "Close the current special buffer." })
	end,
})

-- AUTOCMD: Add 'q' keymap for netrw buffers.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "netrw" },
	callback = function()
		-- Remove the netrw buffer when it is hidden.
		--
		-- For more info on why this is necessary, see:
		-- https://vi.stackexchange.com/questions/14622/how-can-i-close-the-netrw-buffer
		vim.bo.bufhidden = "wipe"

		-- KEYMAP(N): q
		vim.keymap.set("n", "q", ":bd<cr>", { buffer = true, desc = "Close the netrw window.", nowait = true })
	end,
})
