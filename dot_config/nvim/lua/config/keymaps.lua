-- P1: Add keymaps that give you back ';' and ',' functionality!
-- P1: Implement y* maps that copy parts of filename.
-- P2: Prefix every keymap command with a KEYMAP comment!
-- P2: Add fugitive keymaps!

local kill_buffer = require("util.kill_buffer").kill_buffer

--- Function to remove the current file using 'trash' with a fallback of 'rm'.
---
---@return boolean # Whether the file was removed successfully.
local function delete_file()
	-- Get the current file's full path
	local filename = vim.fn.expand("%:p")

	-- Remove the current buffer and navigate back to the last active buffer.
	kill_buffer("#")

	-- Create a temporary file for stderr.
	local stderr_file = os.tmpname()

	-- Try to trash the file first.
	local command_name = "trash"
	local trash_success = os.execute(command_name .. " " .. vim.fn.shellescape(filename) .. " 2> " .. stderr_file)

	--- Notify the user that the trash/rm command failed (include error message).
	---
	---@param cmd_name string The name of the command that failed.
	local function notify_cmd_failed(cmd_name)
		local err_msg = io.open(stderr_file, "r"):read("*a")
		vim.notify(err_msg, vim.log.levels.WARN, { title = "'" .. cmd_name .. "' error message" })
	end

	-- If trash command fails, try using rm as fallback.
	if trash_success ~= 0 then
		notify_cmd_failed(command_name)

		command_name = "rm"
		local rm_success = os.execute(command_name .. " " .. vim.fn.shellescape(filename) .. " 2> " .. stderr_file)

		-- If both commands fail, show error message.
		if rm_success ~= 0 then
			notify_cmd_failed(command_name)
			vim.notify("Failed to delete file: " .. filename, vim.log.levels.ERROR)
			return false
		end
	end

	vim.notify("Deleted file using '" .. command_name .. "': " .. filename, vim.log.levels.INFO)
	return true
end

--- Command-line maps / abhreviations.
--
-- KEYMAP(C): %% (Expand %% to current buffer's parent directory.)
vim.cmd("cnoremap <expr> %% getcmdtype() == ':' ? expand('%:h').'/' : '%%'")
-- KEYMAP(C): w!!
vim.keymap.set(
	"c",
	"w!!",
	"w !sudo tee > /dev/null %",
	{ desc = "Save the current file with elevated (using sudo) permissions." }
)

-- KEYMAP(N+V): ;
vim.keymap.set({ "n", "v" }, ";", ":", { desc = "Map semicolon to colon." })

-- Maps to save / exit.
--
-- P2: Add KEYMAP comments to save/exit keymaps!
vim.keymap.set({ "n", "i" }, "<leader>e", "<esc>:x!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>E", "<esc>:xa!<cr>")
vim.keymap.set({ "n", "i" }, "<leader>s", "<esc>:update<cr>")

-- Maps that make buffer navigation easier.
--
-- P1: Change '-', '|', '_', and '+' map defaults to lowest buffer num (NOT 1).
-- P2: Fix BROKEN '+' map?!
-- P2: Add KEYMAP comments to '-', '_', '|', and '+' keymaps!
vim.keymap.set("n", "_", ':<C-u>execute "sbuffer " . v:count1<CR>')
vim.keymap.set("n", "|", ':<C-u>execute "vert sbuffer " . v:count1<CR>')
vim.keymap.set("n", "+", ':<C-u>execute "tab sbuffer " . v:count<CR>')
vim.keymap.set("n", "-", ':<C-u>execute "buffer " . v:count1<CR>')

-- KEYMAP(N): <C-\>
vim.keymap.set("n", "<C-\\>", "<C-^>", { desc = "Navigate to alternate file." })

-- KEYMAP(V): <space>
vim.keymap.set("v", "<space>", "$<left>", { desc = "Visual map to go to the end of the line." })

-- Configure LSP maps.
--
-- P2: Add KEYMAP comments to LSP keymaps!
local lsp_opts = { noremap = true, silent = true }
vim.keymap.set("n", "<leader>rn", "<cmd>lua vim.lsp.buf.rename()<CR>", lsp_opts)
vim.keymap.set("n", "<leader>ca", "<cmd>lua vim.lsp.buf.code_action()<CR>", lsp_opts)
vim.keymap.set("n", "K", "<cmd>lua vim.lsp.buf.hover()<CR>", lsp_opts)
vim.keymap.set("n", "g0", "<cmd>lua vim.lsp.buf.document_symbol()<CR>", lsp_opts)
vim.keymap.set("n", "gW", "<cmd>lua vim.lsp.buf.workspace_symbol()<CR>", lsp_opts)
vim.keymap.set("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>", lsp_opts)
vim.keymap.set("n", "gD", "<cmd>lua vim.lsp.buf.declaration()<CR>", lsp_opts)
vim.keymap.set("n", "gi", "<cmd>lua vim.lsp.buf.implementation()<CR>", lsp_opts)
vim.keymap.set("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", lsp_opts)
vim.keymap.set("n", "<C-k>", "<cmd>lua vim.lsp.buf.signature_help()<CR>", lsp_opts)
vim.keymap.set("n", "gt", "<cmd>lua vim.lsp.buf.type_definition()<CR>", lsp_opts)
vim.keymap.set("n", "[d", "<cmd>lua vim.diagnostic.goto_prev()<CR>", lsp_opts)
vim.keymap.set("n", "]d", "<cmd>lua vim.diagnostic.goto_next()<CR>", lsp_opts)

-- KEYMAP(N): <leader>/
vim.keymap.set("n", "<leader>/", "/\\v\\C<><Left>", { desc = "Map to search for a <WORD>." })

-- KEYMAP(N): <leader>dd
vim.keymap.set("n", "<leader>dd", function()
	kill_buffer("#")
end, { desc = "Remove the current buffer and navigate back to the last active buffer." })
-- KEYMAP(N): <leader>dn
vim.keymap.set("n", "<leader>dn", function()
	kill_buffer("next")
end, { desc = "Remove the current buffer and navigate to the next buffer." })
-- KEYMAP(N): <leader>dp
vim.keymap.set("n", "<leader>dp", function()
	kill_buffer("prev")
end, { desc = "Remove the current buffer and navigate to the previous buffer." })

-- KEYMAP(N): <leader>D
vim.keymap.set("n", "<leader>D", delete_file, {
	desc = "Removes a file using 'trash' with a fallback of 'rm'.",
})

-- KEYMAP(N): [w
vim.keymap.set("n", "[w", function()
	-- Store current word
	local current_word = vim.fn.expand("<cword>")
	vim.cmd('normal! "_yiw')

	-- Search backwards for a word boundary
	local ok = pcall(function()
		vim.fn.search("\\w\\+\\_W\\+\\%#", "b")
	end)

	if ok then
		-- Perform the swap using substitute
		vim.cmd([[silent! s/\(\%#\w\+\)\(\_W\+\)\(\w\+\)/\3\2\1/]])

		-- Clear search highlighting
		vim.cmd("nohlsearch")

		-- Move cursor to swapped the word
		vim.fn.search("\\V\\<" .. vim.fn.escape(current_word, "\\") .. "\\>")
	end
end, { desc = "Swap the current word with previous word.", silent = true })

-- KEYMAP(N): ]w
vim.keymap.set("n", "]w", function()
	-- Store current word
	local current_word = vim.fn.expand("<cword>")
	vim.cmd('normal! "_yiw')

	-- Perform the swap using substitute
	vim.cmd([[silent! s/\(\%#\w\+\)\(\_W\+\)\(\w\+\)/\3\2\1/]])

	-- Clear search highlighting and find the swapped word
	vim.cmd("nohlsearch")
	vim.fn.search("\\V\\<" .. vim.fn.escape(current_word, "\\") .. "\\>")
end, { desc = "Swap the current word with next word.", silent = true })

-- KEYMAP(N): gV
vim.keymap.set("n", "gV", "ggVG", { desc = "Map to select the entire contents of the current file." })

-- KEYMAP(N): <leader><space>
vim.keymap.set(
	"n",
	"<leader><space>",
	"a<Space><Esc>hi<Space><Esc>l",
	{ desc = "Map to insert space before and after character under cursor." }
)

-- KEYMAP(N): <leader>v
vim.keymap.set("n", "<leader>v", function()
	-- NOTE: We MUST store this count before calling `vim.cmd("normal V")`!
	local count
	if vim.v.count > 0 then
		count = vim.v.count
	else
		count = 1
	end
	vim.cmd("normal V" .. count .. "j")
end, { desc = "Map to visually select next N lines (N defaults to 1 or v:count)." })

-- KEYMAP(N): <c-l>
vim.keymap.set("n", "<C-l>", function()
	vim.cmd("nohlsearch")
	vim.cmd("redraw")
end, { silent = true, desc = "Disable search highlighting temporarily (until the next search)." })

-- KEYMAP(N+V): &
--
-- Used to preserve the flags of the last substitution.
vim.cmd("nnoremap & :&&<CR>")
vim.cmd("xnoremap & :&&<CR>")
