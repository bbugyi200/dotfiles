--- This is a reader that puts the content of each input file into a code
--- block, sets the file’s extension as the block’s class to enable code
--- highlighting, and places the filename as a header above each code block.
---
--- Taken from ~/org/lib/manual/pandoc_custom_rw.pdf

local pandoc = require("pandoc")
local header_idx = 0

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

function Reader(input, _)
	return pandoc.Pandoc(input:map(to_code_block))
end
