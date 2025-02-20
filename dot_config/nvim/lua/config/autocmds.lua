-- P2: Add all of my 'autocmds' to the same group to support `:Telescope autocmd`?!
local delete_file = require("util.delete_file")

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
---
---@param close_window_if_multiple boolean Whether to close the window if there are multiple windows.
local function quit_special_buffer(close_window_if_multiple)
	local altfile = vim.fn.expand("%")
	local listed_buffers = vim.fn.getbufinfo({ buflisted = 1 })
	if altfile ~= "" and vim.fn.filereadable(altfile) then
		vim.cmd("b#")
		-- HACK: Run 'edit' to reload the buffer, which fixes some highlighting
		-- issues at times. Check if the buffer is changed first to avoid "No
		-- write since last change" error.
		if vim.fn.getbufinfo(vim.fn.bufname())[1].changed ~= 1 then
			vim.cmd("edit")
		end
	elseif #listed_buffers > 1 then
		vim.cmd("bd")
	else
		vim.cmd("q")
	end

	if close_window_if_multiple and #vim.api.nvim_list_wins() > 1 then
		vim.cmd("wincmd c")
	end
end

--- Quits a "fake buffer" and closes the window if there are multiple windows.
local function quit_and_close_special_buffer()
	quit_special_buffer(true)
end

--- Fetch the path of the file under the cursor in a netrw buffer.
---
---@return string # The absolute path of the file under the cursor in a netrw buffer.
local function get_path_of_netrw_file()
	local line = vim.fn.getline(".")
	local split_lines = vim.split(line, "%s+", { trip_empty = true })
	-- If we are using the tree view, the path is in the second column.
	if split_lines[1] == "|" then
		line = split_lines[2]
	else
		line = split_lines[1]
	end
	return vim.fs.joinpath(vim.b.netrw_curdir, line)
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

-- AUTOCMD: Configuration that is specific to 'help' buffers.
vim.api.nvim_create_autocmd("BufWinEnter", {
	callback = function()
		-- Abort if the buffer is not a help buffer.
		if vim.bo.buftype ~= "help" then
			return
		end

		-- KEYMAP(N): q
		vim.keymap.set("n", "q", quit_and_close_special_buffer, {
			buffer = true,
			desc = "Close the help buffer.",
		})
		-- KEYMAP(N): Q
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

-- AUTOCMD: Configuration that is specific to 'quickfix' buffers.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "qf" },
	callback = function()
		-- KEYMAP(N): q
		vim.keymap.set("n", "q", quit_and_close_special_buffer, {
			buffer = true,
			desc = "Close the quickfix buffer.",
		})
		-- KEYMAP(N): Q
		vim.keymap.set("n", "Q", function()
			-- If we are in the location list...
			if vim.fn.get(vim.fn.getloclist(0, { winid = 0 }), "winid", 0) ~= 0 then
				vim.cmd("lclose | Trouble loclist")
			-- Otherwise, we are in the quickfix list.
			else
				vim.cmd("cclose | Trouble quickfix")
			end
		end, { buffer = true, desc = "Send the quickfix results to Trouble." })
	end,
})

-- AUTOCMD: Configuration that is specific to 'fugitive' buffers.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "fugitive" },
	callback = function()
		-- KEYMAP(N): q
		vim.keymap.set("n", "q", quit_and_close_special_buffer, {
			buffer = true,
			desc = "Close the fugitive buffer.",
		})
	end,
})

-- AUTOCMD: Configuration that is specific to treesitter 'query' buffers.
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "query" },
	callback = function()
		-- KEYMAP(N): q
		vim.keymap.set("n", "q", quit_and_close_special_buffer, {
			buffer = true,
			desc = "Close the treesitter query buffer.",
		})
	end,
})

-- AUTOCMD: Configuration that is specific to 'netrw' buffers.
--
-- P2: Add ,y*; ,m*; and ,c* keymaps to netrw buffers?
vim.api.nvim_create_autocmd("FileType", {
	pattern = { "netrw" },
	callback = function()
		-- Remove the netrw buffer when it is hidden.
		--
		-- For more info on why this is useful, see:
		-- https://vi.stackexchange.com/questions/14622/how-can-i-close-the-netrw-buffer
		vim.bo.bufhidden = "wipe"

		-- KEYMAP(N): q
		vim.keymap.set(
			"n",
			"q",
			quit_special_buffer,
			{ buffer = true, desc = "Close the netrw window.", nowait = true }
		)

		-- KEYMAP(N): <tab>
		vim.keymap.set("n", "<tab>", "<cmd>normal mfj<cr>", {
			desc = "Toggle mark for current file and move cursor to next file.",
		})
		-- KEYMAP(N): <s-tab>
		vim.keymap.set("n", "<s-tab>", "<cmd>normal mfk<cr>", {
			desc = "Toggle mark for current file and move cursor to previous file.",
		})
		-- KEYMAP(N): D
		vim.keymap.set({ "n", "v" }, "D", function()
			delete_file(get_path_of_netrw_file())
			vim.cmd("edit") -- refreshes netrw buffer so that the file is removed from the list
		end, { buffer = true, desc = "Delete the file under the cursor." })

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
