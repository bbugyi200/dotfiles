--- Filetype: zorg

local legacy_filetypes = {
	["zorg.jinja"] = true,
	["zorg.zorq"] = true,
}

local legacy_extensions = {
	zo = true,
	zoq = true,
	zot = true,
}

local filetype = vim.bo.filetype
local extension = vim.fn.expand("%:e")

if legacy_filetypes[filetype] or legacy_extensions[extension] then
	require("legacy_zorg.config")
end
