-- Configure LSP autocmds
vim.api.nvim_command("augroup LSP")
vim.api.nvim_command("autocmd!")
vim.api.nvim_command("autocmd CursorHold  <buffer> lua vim.lsp.buf.document_highlight()")
vim.api.nvim_command("autocmd CursorHoldI <buffer> lua vim.lsp.buf.document_highlight()")
vim.api.nvim_command("autocmd CursorMoved <buffer> lua vim.lsp.util.buf_clear_references()")
vim.api.nvim_command("augroup END")

local chezmoi_dir = os.getenv("HOME") .. "/.local/share/chezmoi"
vim.api.nvim_create_autocmd("BufWritePost", {
	pattern = {
		chezmoi_dir .. "/*",
		"/tmp/chezmoi-edit*",
	},
	command = "!chezmoi apply",
	group = vim.api.nvim_create_augroup("ChezmoiAutoApply", { clear = true }),
	desc = "Apply chezmoi automatically after writing to chezmoi-managed files",
})

vim.api.nvim_create_autocmd("BufWritePost", {
	pattern = "*.lua",
	group = vim.api.nvim_create_augroup("AutoFormatLua", { clear = true }),
	desc = "Run stylua on save for Lua files",
	callback = function(args)
		-- `args.file` (or `vim.fn.expand("<afile>")`) holds the path of the saved file
		local file = args.file

		-- Escape the filename in case it has spaces, etc.
		-- (Using fnameescape is safer than naive string concatenation)
		local escaped_file = vim.fn.fnameescape(file)

		-- Run stylua as an external command, then reload the file.
		vim.fn.system(string.format("stylua %s", escaped_file))
		vim.cmd("edit!")
	end,
})
