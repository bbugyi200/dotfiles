local assert = require("busted").assert
local describe = require("busted").describe
local it = require("busted").it

describe("Can source config/*.lua modules", function()
	it("init.lua", function()
		assert.are.equal(1 + 2, 3)
	end)
end)
