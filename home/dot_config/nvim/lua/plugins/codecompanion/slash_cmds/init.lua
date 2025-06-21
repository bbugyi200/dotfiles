--- Custom CodeCompanion slash commands (for work and personal) live in this module.

local group_cmds = require("plugins.codecompanion.slash_cmds.group_cmds")

return {
	favs = require("plugins.codecompanion.slash_cmds.favs"),
	load_group = group_cmds.load_group,
	save_group = group_cmds.save_group,
}
