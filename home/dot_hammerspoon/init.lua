hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "V", nil, function()
	local paste_parts = os.getenv("HOME") .. "/bin/paste_parts"
	hs.task.new("/bin/bash", nil, { "-l", "-c", paste_parts }):start()
end)

hs.hotkey.bind({ "cmd", "shift" }, "i", nil, function()
	local target = os.getenv("HOME") .. "/bob/mac_inbox.zo"
	local button, text = hs.dialog.textPrompt("Capture task", "Task text:", "", "Add", "Cancel")
	if button ~= "Add" then
		return
	end
	text = (text or ""):gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", "")
	if text == "" then
		return
	end
	local f = io.open(target, "a")
	if not f then
		hs.notify.show("Task capture failed", "", target)
		return
	end
	f:write("- [ ] #task " .. text .. "\n")
	f:close()
	hs.notify.show("Captured task", "", text)
end)
