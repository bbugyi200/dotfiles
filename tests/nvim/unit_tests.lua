local assert = require("busted").assert
local describe = require("busted").describe
local it = require("busted").it
local pending = require("busted").pending

describe("UNIT TEST:", function()
	-- P4: TEST: flexes bb_utils.delete_file()
	pending("bb_utils.delete_file()")
	-- P4: TEST: flexes bb_utils.copy_to_clipboard()
	pending("bb_utils.copy_to_clipboard()")

	it("selects tmux-osc52 on Linux inside tmux", function()
		local clipboard_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/clipboard.lua"
		local provider = assert(dofile(clipboard_path))
		local got = provider({ is_mac = false, tmux = true })

		assert.is_not_nil(got)
		assert.is_equal("tmux-osc52", got.name)
		assert.are.same({ "tmux", "load-buffer", "-w", "-" }, got.copy["+"])
		assert.are.same({ "tmux", "load-buffer", "-w", "-" }, got.copy["*"])
		assert.are.same({ "sh", "-c", "tmux save-buffer - 2>/dev/null || true" }, got.paste["+"])
		assert.are.same({ "sh", "-c", "tmux save-buffer - 2>/dev/null || true" }, got.paste["*"])
		assert.is_equal(0, got.cache_enabled)
	end)

	it("returns nil on macOS so Neovim keeps the native clipboard", function()
		local clipboard_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/clipboard.lua"
		local provider = assert(dofile(clipboard_path))

		assert.is_nil(provider({ is_mac = true, tmux = true }))
		assert.is_nil(provider({ is_mac = true, tmux = false }))
	end)

	it("returns nil on Linux outside tmux so Neovim keeps auto-detection", function()
		local clipboard_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/clipboard.lua"
		local provider = assert(dofile(clipboard_path))

		assert.is_nil(provider({ is_mac = false, tmux = false }))
	end)

	it("pins vim.g.clipboard from config.clipboard before UIEnter", function()
		local options_path = (os.getenv("PWD") or "") .. "/home/dot_config/nvim/lua/config/options.lua"
		local handle = assert(io.open(options_path, "r"))
		local contents = handle:read("*all")
		handle:close()

		local provider_at = contents:find('require%("config%.clipboard"%)', 1)
		local uienter_at = contents:find("UIEnter", 1, true)
		assert.is_truthy(provider_at)
		assert.is_truthy(uienter_at)
		assert.is_true(provider_at < uienter_at)
	end)

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
