--- Configure keymaps that are NOT specific to a plugin.
--
-- P1: Add keymaps that give you back ';' and ',' functionality!
-- P2: Add <c-h> (or <c-t>?) command mode keymap for command-line history selection
--     (uses the current contents of the command line to populate a Telescope history search!)
-- P2: Prefix every keymap command with a KEYMAP comment!
-- P2: Give the keymaps/*.lua modules better names?

require("config.keymaps.delete")
require("config.keymaps.misc")
require("config.keymaps.nav")
require("config.keymaps.yank")
