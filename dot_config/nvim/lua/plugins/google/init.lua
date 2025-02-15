-- P1: Use vim.tbl_extend() instead of merge_tables()!
-- P2: Replace merge_tablees with NeoVim's built-in table (vim.tbl_extend or
--     something like that?) concatenation.
-- P2: Install ALL plugins listed in go/neovim!
-- P2: Flex critique plugins!
-- P2: Configure http://go/analysislsp-neovim !
-- P2: Add neocitc integrations described by
--     https://team.git.corp.google.com/neovim-dev/neocitc/+/refs/heads/main

local is_goog_machine = require("util.is_goog_machine").is_goog_machine

--- Performs an in-place merge of two array-like Lua tables.
---
---@generic T : table
---@param t1 T The first table to merge, which will be modified in-place.
---@param t2 T The second table to merge.
---@return T # The 1st table (t1) with the contents of the 2nd table (t2) merged in.
local function merge_tables(t1, t2)
	table.move(t2, 1, #t2, #t1 + 1, t1)
	return t1
end

if is_goog_machine() then
	return merge_tables(require("plugins.google.glugs"), require("plugins.google.non_glugs"))
else
	return {}
end
