local MODULE_PATH = "home/dot_hammerspoon/mac_notify.lua"

local function setup(options)
	options = options or {}
	local env = { previous_hs = _G.hs, tasks = {}, timers = {}, logs = {}, options = options }
	local hs = { task = {}, timer = {} }

	function hs.printf(...)
		table.insert(env.logs, { ... })
	end

	function hs.task.new(command, callback, args)
		if options.create_error then
			error(options.create_error)
		end
		if options.create_nil then
			return nil
		end
		local task = {
			command = command,
			callback = callback,
			args = args,
			running = false,
			terminated = false,
		}
		function task:setEnvironment(environment)
			self.environment = environment
		end
		function task:start()
			self.started = true
			if options.start_error then
				error(options.start_error)
			end
			if options.start_false then
				return false
			end
			self.running = true
			return true
		end
		function task:isRunning()
			return self.running and not self.terminated
		end
		function task:terminate()
			self.terminated = true
			self.running = false
		end
		function task:complete(exit_code, stdout, stderr)
			self.running = false
			if self.callback then
				self.callback(exit_code, stdout, stderr)
			end
		end
		table.insert(env.tasks, task)
		return task
	end

	hs.timer.doAfter = function(delay, callback)
		local timer = { delay = delay, callback = callback, stopped = false }
		function timer:stop()
			self.stopped = true
		end
		table.insert(env.timers, timer)
		return timer
	end

	_G.hs = hs
	local module = assert(loadfile(MODULE_PATH))()
	function env.restore()
		_G.hs = env.previous_hs
	end
	return env, module
end

describe("macOS notification poster", function()
	local env, local_notify

	after_each(function()
		if env then
			env.restore()
			env = nil
		end
	end)

	it("passes text through argv and sets the task environment", function()
		env, local_notify = setup()
		local title = 'title"; do shell script "false'
		local subtitle = "a subtitle"
		local body = "body with a newline\nand semicolon;"
		local task = local_notify.post(title, subtitle, body)
		assert.equals("/usr/bin/osascript", task.command)
		assert.same({ "-e", task.args[2], title, subtitle, body }, task.args)
		assert.is_truthy(task.args[2]:find("item 1 of argv", 1, true))
		assert.is_truthy(task.args[2]:find("item 2 of argv", 1, true))
		assert.is_truthy(task.args[2]:find("item 3 of argv", 1, true))
		assert.is_nil(task.args[2]:find(title, 1, true))
		assert.same(
			{ PATH = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", HOME = os.getenv("HOME") or "" },
			task.environment
		)
	end)

	it("reports successful and failed task exits once", function()
		env, local_notify = setup()
		local calls = {}
		local task = local_notify.post("title", "", "body", function(...)
			table.insert(calls, { ... })
		end)
		task:complete(0, "", "")
		task:complete(1, "", "later")
		assert.equals(1, #calls)
		assert.same({ true, 0, "" }, calls[1])
		assert.is_true(env.timers[1].stopped)

		local failed_calls = {}
		local failed = local_notify.post("title", "", "body", function(...)
			table.insert(failed_calls, { ... })
		end)
		failed:complete(17, "", "denied")
		assert.same({ { false, 17, "denied" } }, failed_calls)
	end)

	it("reports task creation and start failures", function()
		env, local_notify = setup({ create_error = "spawn failed" })
		local create_calls = {}
		assert.is_nil(local_notify.post("title", "", "body", function(...)
			table.insert(create_calls, { ... })
		end))
		assert.equals(1, #create_calls)
		assert.is_false(create_calls[1][1])
		assert.is_truthy(create_calls[1][3]:find("spawn failed", 1, true))
		assert.is_true(#env.logs > 0)

		env.restore()
		env, local_notify = setup({ start_false = true })
		local start_calls = {}
		assert.is_nil(local_notify.post("title", "", "body", function(...)
			table.insert(start_calls, { ... })
		end))
		assert.equals(1, #start_calls)
		assert.is_false(start_calls[1][1])
		assert.is_truthy(start_calls[1][3]:find("could not start", 1, true))
	end)

	it("terminates hung tasks and calls completion only once", function()
		env, local_notify = setup()
		local calls = {}
		local task = local_notify.post("title", "", "body", function(...)
			table.insert(calls, { ... })
		end)
		assert.equals(5, env.timers[1].delay)
		env.timers[1].callback()
		task:complete(0, "", "late")
		assert.is_true(task.terminated)
		assert.equals(1, #calls)
		assert.same({ false, nil, "notification task timed out" }, calls[1])
	end)

	it("retains live tasks until completion and releases them afterward", function()
		env, local_notify = setup()
		-- Do not retain the timer callback here; this isolates the module's task table.
		_G.hs.timer.doAfter = function()
			return { stop = function() end }
		end
		local task = local_notify.post("title", "", "body")
		local weak_task = setmetatable({ task }, { __mode = "v" })
		env.tasks[1] = nil
		task = nil
		collectgarbage("collect")
		assert.is_not_nil(weak_task[1])
		weak_task[1]:complete(0, "", "")
		weak_task[1] = nil
		collectgarbage("collect")
		assert.is_nil(weak_task[1])
	end)
end)
