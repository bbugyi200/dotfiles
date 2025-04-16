local search = require("zorg.util.search")

--- Numbers and formats a list of options for a prompt.
---
---@param option_values table<string> A list of option values.
---@return table<string> # A list of numbered options, ready to be displayed.
local function get_pretty_options(option_values)
	local new_list = { "" }
	for index, item in ipairs(option_values) do
		table.insert(new_list, "  " .. index .. ") " .. item)
	end
	table.insert(new_list, "")
	return new_list
end

--- Open a Zorg link using 'zorg action open'.
---
---@param count integer A count used to specify a specific target (left-to-right).
---@param option_idx integer? The index of the option to select (if a prompt is required).
local function run_open_zorg_action(count, option_idx)
	-- Save the current buffer if necessary.
	vim.cmd("update")

	if count > 0 then
		vim.cmd("normal! mm" .. tostring(count) .. "gj")
	elseif count < 0 then
		vim.cmd("normal! mm" .. tostring(-count) .. "gk")
	end

	local curr_line_no = vim.fn.line(".")
	local curr_file = vim.fn.expand("%")

	if count ~= 0 then
		vim.cmd("normal! 'm")
	end

	local cmd_base = "zorg --log=null --log=+zorg_actions@nocolor action open "
		.. curr_file
		.. " "
		.. tostring(curr_line_no)
	local cmd = option_idx == nil and cmd_base or (cmd_base .. " " .. tostring(option_idx))

	repeat
		local zorg_out = vim.fn.system(cmd)
		cmd = ""

		for _, open_action_msg_line in ipairs(vim.fn.split(zorg_out, "\n")) do
			local open_action_msg = vim.fn.split(open_action_msg_line)
			if open_action_msg[1] == "EDIT" then
				vim.cmd("edit " .. open_action_msg[2])
			elseif open_action_msg[1] == "ECHO" then
				print("[ZORG] " .. table.concat(vim.fn.slice(open_action_msg, 1), " "))
			elseif open_action_msg[1] == "SEARCH" then
				-- Assuming Search is some other function defined in Lua
				search(open_action_msg[2])
			elseif open_action_msg[1] == "PROMPT" then
				vim.cmd("clear")
				local option_values = vim.fn.slice(open_action_msg, 1)
				local pretty_options = get_pretty_options(option_values)

				-- Use inputlist instead of vim.ui.input as it's synchronous
				local opt_idx = vim.fn.inputlist(pretty_options)

				if opt_idx > 0 and opt_idx <= #option_values then
					cmd = cmd_base .. " " .. tostring(opt_idx)
				else
					vim.notify("Invalid option selected", vim.log.levels.WARN)
					cmd = ""
				end
			end
		end
	until cmd == ""
end

return run_open_zorg_action
