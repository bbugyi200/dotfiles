hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "V", nil, function()
	local text = hs.pasteboard.getContents()
	if not text or text == "" then
		hs.alert.show("Clipboard is empty")
		return
	end

	local numWords = 5
	local sleepDelay = 0.1

	-- Build a list of actions: each is either {type="paste", chunk=...} or {type="newline"}.
	local actions = {}

	-- Split text into lines, preserving empty lines.
	local lines = {}
	for line in text:gmatch("([^\n]*)\n?") do
		table.insert(lines, line)
	end
	-- Remove trailing empty entry produced by the pattern when text ends with \n.
	if #lines > 0 and lines[#lines] == "" then
		table.remove(lines)
	end

	for lineIdx, line in ipairs(lines) do
		-- Simulate Shift+Enter before each line except the first.
		if lineIdx > 1 then
			table.insert(actions, { type = "newline" })
		end

		-- Split line into words.
		local words = {}
		for word in line:gmatch("%S+") do
			table.insert(words, word)
		end

		-- Empty line: newline already queued above, nothing else to paste.
		if #words > 0 then
			local i = 1
			while i <= #words do
				local chunkWords = {}
				for j = i, math.min(i + numWords - 1, #words) do
					table.insert(chunkWords, words[j])
				end
				local chunk = table.concat(chunkWords, " ")

				-- Append trailing space if not the last chunk on this line.
				if i + numWords <= #words then
					chunk = chunk .. " "
				end

				table.insert(actions, { type = "paste", chunk = chunk })
				i = i + numWords
			end
		end
	end

	if #actions == 0 then
		hs.alert.show("Clipboard is empty")
		return
	end

	local actionIdx = 1
	local function processNextAction()
		if actionIdx > #actions then
			-- Restore original clipboard contents.
			hs.pasteboard.setContents(text)
			return
		end

		local action = actions[actionIdx]
		if action.type == "newline" then
			hs.eventtap.keyStroke({ "shift" }, "return")
		else
			hs.pasteboard.setContents(action.chunk)
			hs.eventtap.keyStroke({ "cmd" }, "v")
		end

		actionIdx = actionIdx + 1
		hs.timer.doAfter(sleepDelay, processNextAction)
	end

	processNextAction()
end)
