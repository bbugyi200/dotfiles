local is_goog_machine = require("util.is_goog_machine")

if is_goog_machine() then
	-- Use vim.list_extend to merge the two arrays of plugins
	return vim.list_extend(require("plugins.google.glugs"), require("plugins.google.non_glugs"))
else
	return {}
end
