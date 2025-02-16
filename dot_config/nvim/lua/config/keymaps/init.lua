--- Configure keymaps that are NOT specific to a plugin.
--
-- P2: Add <c-h> (or <c-t>?) command mode keymap for command-line history selection
--     (uses the current contents of the command line to populate a Telescope history search!)
-- P2: Prefix every keymap command with a KEYMAP comment!

require("config.keymaps.core")
require("config.keymaps.delete_buffers")
require("config.keymaps.nav_buffers")
require("config.keymaps.yank_path")
