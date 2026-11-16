-- Post macOS notification banners through osascript. Hammerspoon's notification
-- API is accepted by NotificationCenter on this Mac but never presented.
local M = {}

local live_tasks = {}
local TIMEOUT_SECONDS = 5
local TASK_PATH = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
local SCRIPT = [[
on run argv
	display notification (item 3 of argv) with title (item 1 of argv) subtitle (item 2 of argv)
end run
]]

local function log_message(format, ...)
	if hs and type(hs.printf) == "function" then
		hs.printf("Mac notification " .. format, ...)
	end
end

local function stop_timer(timer)
	if timer and type(timer.stop) == "function" then
		pcall(function()
			timer:stop()
		end)
	end
end

function M.post(title, subtitle, body, on_done)
	local completed = false
	local task
	local timer

	local function finish(ok, exit_code, stderr)
		if completed then
			return
		end
		completed = true
		stop_timer(timer)
		if task then
			live_tasks[task] = nil
		end
		if type(on_done) == "function" then
			local callback_ok, callback_error = pcall(on_done, ok, exit_code, stderr)
			if not callback_ok then
				log_message("completion callback failed: %s", callback_error)
			end
		end
	end

	local created, result = pcall(function()
		return hs.task.new("/usr/bin/osascript", function(exit_code, _stdout, stderr)
			finish(exit_code == 0, exit_code, stderr)
		end, { "-e", SCRIPT, tostring(title or ""), tostring(subtitle or ""), tostring(body or "") })
	end)
	if not created or not result then
		log_message("osascript task could not be created: %s", created and "no task returned" or result)
		finish(false, nil, created and "could not create task" or tostring(result))
		return nil
	end
	task = result
	live_tasks[task] = task

	local environment_ok, environment_error = pcall(function()
		if task.setEnvironment then
			task:setEnvironment({ PATH = TASK_PATH, HOME = os.getenv("HOME") or "" })
		end
	end)
	if not environment_ok then
		log_message("could not set task environment: %s", environment_error)
	end

	local start_ok, started = pcall(function()
		return task:start()
	end)
	if not start_ok or not started then
		log_message("osascript task could not be started: %s", start_ok and "start returned false" or started)
		finish(false, nil, start_ok and "could not start task" or tostring(started))
		return nil
	end

	if hs.timer and type(hs.timer.doAfter) == "function" and not completed then
		timer = hs.timer.doAfter(TIMEOUT_SECONDS, function()
			local running_ok, running = pcall(function()
				return task:isRunning()
			end)
			if running_ok and running then
				pcall(function()
					task:terminate()
				end)
				log_message("osascript task timed out after %d seconds", TIMEOUT_SECONDS)
				finish(false, nil, "notification task timed out")
			end
		end)
	end
	return task
end

return M
