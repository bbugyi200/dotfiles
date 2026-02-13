hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "V", nil, function()
	local text = hs.pasteboard.getContents()
	if not text or text == "" then
		hs.alert.show("Clipboard is empty")
		return
	end

	local numWords = 5
	local sleepDelay = 0.1

	local words = {}
	for word in text:gmatch("%S+") do
		table.insert(words, word)
	end

	if #words == 0 then
		hs.alert.show("Clipboard is empty")
		return
	end

	local i = 1
	local function pasteNextChunk()
		if i > #words then
			hs.pasteboard.setContents(text)
			return
		end

		local chunkWords = {}
		for j = i, math.min(i + numWords - 1, #words) do
			table.insert(chunkWords, words[j])
		end
		local chunk = table.concat(chunkWords, " ")

		if i + numWords <= #words then
			chunk = chunk .. " "
		end

		hs.pasteboard.setContents(chunk)
		hs.eventtap.keyStroke({ "cmd" }, "v")

		i = i + numWords
		hs.timer.doAfter(sleepDelay, pasteNextChunk)
	end

	pasteNextChunk()
end)
