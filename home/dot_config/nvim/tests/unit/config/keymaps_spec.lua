local assert = require("busted").assert
local describe = require("busted").describe
local it = require("busted").it

describe("Test example", function()
	it("Test can add numbers", function()
		assert.are.same(1 + 2, 3)
	end)
end)
