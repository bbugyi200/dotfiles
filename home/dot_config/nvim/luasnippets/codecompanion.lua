-- Snippets for CodeCompanion chat buffer.

local bb = require("bb_utils")

local cc_snippets = {}
return vim.tbl_extend("force", cc_snippets, bb.snip.get_markdown_snippets())
