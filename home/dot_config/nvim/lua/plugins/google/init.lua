-- P1: Use vim.tbl_extend() instead of merge_tables()!
-- P2: Install ALL plugins listed in go/neovim!
-- P2: Flex critique plugins!
-- P2: Configure http://go/analysislsp-neovim !
-- P2: Add neocitc integrations described by
--     https://team.git.corp.google.com/neovim-dev/neocitc/+/refs/heads/main

local is_goog_machine = require("util.is_goog_machine")

if is_goog_machine() then
	-- Use vim.list_extend to merge the two arrays of plugins
	return vim.list_extend(require("plugins.google.glugs"), require("plugins.google.non_glugs"))
else
	return {}
end
