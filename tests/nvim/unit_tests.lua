local assert = require("busted").assert
local describe = require("busted").describe
local it = require("busted").it
local pending = require("busted").pending

describe("UNIT TEST:", function()
	-- P4: TEST: flexes bb_utils.delete_file()
	pending("bb_utils.delete_file()")
	-- P4: TEST: flexes bb_utils.copy_to_clipboard()
	pending("bb_utils.copy_to_clipboard()")

	it("configures sase-nvim completion and LSP explicitly", function()
		local sase_nvim_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/plugins/sase_nvim.lua"
		local old_sase_preload = package.preload.sase
		local old_sase_loaded = package.loaded.sase
		local setup_opts

		package.loaded.sase = nil
		package.preload.sase = function()
			return {
				setup = function(opts)
					setup_opts = opts
				end,
			}
		end

		local ok, plugin_spec = pcall(dofile, sase_nvim_path)
		if ok then
			plugin_spec[1].config()
		end

		package.preload.sase = old_sase_preload
		package.loaded.sase = old_sase_loaded

		assert.is_true(ok)
		assert.is_true(setup_opts.complete.keymap)
		assert.is_equal("auto", setup_opts.complete.completion_backend)
		assert.is_true(setup_opts.lsp.enabled)
	end)
end)
