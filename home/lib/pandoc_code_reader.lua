--- This is a pandoc reader that puts the content of each input file into a
--- code block, sets the file’s extension as the block’s class to enable code
--- highlighting, and places the filename as a header above each code block.
---
--- Copied from ~/org/lib/manual/pandoc_custom_rw.pdf and modified to add
--- header numbers and line numbers.

local pandoc = require("pandoc")
local header_idx = 0

--- Converts a code source file to a pandoc div containing a header and code block.
---
---@param source any The source file to convert.
---@return any # A pandoc.Div() containing a header and code block.
local function to_code_block(source)
	local _, lang = pandoc.path.split_extension(source.name)
	local source_name = source.name == "" and "<stdin>" or source.name
	header_idx = header_idx + 1

	-- Split the source text into lines
	local lines = {}
	for line in source.text:gmatch("([^\r\n]*)\r?\n?") do
		table.insert(lines, line)
	end

	-- Add line numbers
	local numbered_text = {}
	for i, line in ipairs(lines) do
		table.insert(numbered_text, string.format("%3d | %s", i, line))
	end

	-- Join the numbered lines back into a single string
	local numbered_source = table.concat(numbered_text, "\n")

	return pandoc.Div({
		pandoc.Header(1, tostring(header_idx) .. ". " .. source_name),
		pandoc.CodeBlock(numbered_source, { class = lang }),
	})
end

--- Pandoc Reader that reads a list of source files and converts them to code blocks.
---
---@param input any A list of source files to convert to code blocks.
---@return any # A pandoc.Pandoc() node containing the converted code blocks.
function Reader(input, _)
	return pandoc.Pandoc(input:map(to_code_block))
end
