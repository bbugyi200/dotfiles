--- Custom CodeCompanion slash commands (for work and personal) live in this module.

local group_cmds = require("plugins.codecompanion.slash_cmds.group_cmds")

return {
	load_group = group_cmds.load_group,
	save_group = group_cmds.save_group,
	scratch = require("plugins.codecompanion.slash_cmds.scratch"),
}
