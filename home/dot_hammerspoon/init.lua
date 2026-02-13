hs.hotkey.bind({"cmd", "alt", "ctrl"}, "V", function()
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

  hs.alert.show("Pasting " .. #words .. " words in chunks of " .. numWords .. "...")

  local i = 1
  local function pasteNextChunk()
    if i > #words then
      hs.pasteboard.setContents(text)
      hs.alert.show("Done. Original clipboard restored.")
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
    hs.eventtap.keyStroke({"cmd"}, "v")

    i = i + numWords
    hs.timer.doAfter(sleepDelay, pasteNextChunk)
  end

  -- Short delay to let modifier keys release before first paste
  hs.timer.doAfter(0.2, pasteNextChunk)
end)
