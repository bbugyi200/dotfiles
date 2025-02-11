--- Configure keymaps that are NOT specific to a plugin.
---
--- NOTE: Complicated keymaps (ex: ones that benefit from factoring out
--- functions) SHOULD be defined in a separate config/keymaps/*.lua file!
--
-- P1: Add keymaps that give you back ';' and ',' functionality!
-- P2: Prefix every keymap command with a KEYMAP comment!
-- P2: Give the keymaps/*.lua modules better names?

require("config.keymaps.delete")
require("config.keymaps.misc")
require("config.keymaps.nav")
require("config.keymaps.yank")
