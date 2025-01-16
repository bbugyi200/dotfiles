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

-- Add 'q' keymap to close vimdoc help windows.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "help" },
	callback = function()
		vim.keymap.set("n", "q", "<cmd>q<cr>", { buffer = true, desc = "Close the current :help window." })
	end,
})
