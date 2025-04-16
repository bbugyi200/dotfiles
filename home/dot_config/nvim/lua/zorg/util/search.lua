--- Search for a term in the current buffer without highlighting (see `:h hlsearch`).
---
---@param searchTerm string The term to search for.
---@return integer # The line number where the search term was found, or 0 if not found.
local function search(searchTerm)
	if searchTerm:sub(1, 1) == "?" then
		return vim.fn.search("\\C" .. searchTerm:sub(2), "b")
	else
		return vim.fn.search("\\C" .. searchTerm)
	end
end

return search
