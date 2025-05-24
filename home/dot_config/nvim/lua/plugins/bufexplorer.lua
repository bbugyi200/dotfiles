--- Quickly and easily switch between buffers.

return {
	-- PLUGIN: http://github.com/jlanzarotta/bufexplorer
	{
		"jlanzarotta/bufexplorer",
		init = function()
			vim.g.bufExplorerDisableDefaultKeyMapping = 1
		end,
	},
}
