hs.hotkey.bind({"cmd", "alt", "ctrl"}, "V", function()
  hs.task.new("/bin/bash", nil, {"-l", "-c", "paste_parts"}):start()
end)
