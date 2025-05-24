--- Adds a keymap to highlight lines that exceed the textwidth setting in Vim.

--- Highlight lines that exceed textwidth
local function highlight_too_long_lines()
	-- Link RightMargin highlight group to Error highlight group
	vim.api.nvim_set_hl(0, "RightMargin", { link = "Error" })

	-- If textwidth is not 0, set up a match for text exceeding that width
	if vim.o.textwidth ~= 0 then
		vim.fn.matchadd("RightMargin", "\\%>" .. vim.o.textwidth .. "v.\\+")
	end
end

-- Global state to track if highlighting is enabled
local highlight_toolong_enabled = false
-- Function to toggle highlighting of too long lines
local function toggle_highlight_too_long_lines()
	highlight_toolong_enabled = not highlight_toolong_enabled

	-- Clear the existing autocmd group
	local group = vim.api.nvim_create_augroup("highlight_toolong2", { clear = true })

	if highlight_toolong_enabled then
		-- AUTOCMD: Highlight lines exceeding textwidth
		vim.api.nvim_create_autocmd({ "FileType", "BufEnter" }, {
			group = group,
			callback = highlight_too_long_lines,
		})

		-- Apply highlighting to current buffer
		highlight_too_long_lines()
		vim.notify("Enabled highlighting of lines exceeding textwidth", vim.log.levels.INFO)
	else
		-- Clear highlights in current buffer
		for _, match_id in ipairs(vim.fn.getmatches()) do
			if match_id.group == "RightMargin" then
				vim.fn.matchdelete(match_id.id)
			end
		end
		vim.notify("Disabled highlighting of lines exceeding textwidth", vim.log.levels.INFO)
	end
end

-- KEYMAP: <leader>ll
vim.keymap.set(
	"n",
	"<leader>ll",
	toggle_highlight_too_long_lines,
	{ desc = "Toggle highlighting of lines exceeding textwidth" }
)
