local cc = require("plugins.codecompanion.common")
local slash_cmds = require("plugins.google.codecompanion.slash_cmds")

return vim.tbl_deep_extend("force", cc.common_plugin_config, {
	-- PLUGIN: http://github.com/olimorris/codecompanion.nvim
	{
		config = function()
			local goose = require("plugins.google.codecompanion.goose")
			goose.setup({
				auto_start_backend = false,
				auto_start_silent = false,
				temperature = 0.1,
				endpoint = "http://localhost:8649/predict",
				debug = vim.env.CC_GOOSE_DEBUG ~= nil,
				debug_backend = false,
			})

			require("codecompanion").setup(vim.tbl_deep_extend("force", cc.common_setup_opts, {
				adapters = {
					little_goose = goose.get_adapter("LittleGoose", "goose-v3.5-s", 8192),
					big_goose = goose.get_adapter("BigGoose", "gemini-for-google-2.5-pro", 65536),
				},
				strategies = {
					chat = {
						adapter = "big_goose",
						slash_commands = {
							bugs = slash_cmds.bugs,
							cs = slash_cmds.cs,
							clfiles = slash_cmds.clfiles,
						},
					},
					inline = {
						adapter = "big_goose",
					},
					cmd = {
						adapter = "big_goose",
					},
				},
				opts = {
					system_prompt = function()
						return [[
You are an AI programming assistant named "CodeCompanion". You are currently plugged in to the Neovim text editor on a user's machine.

Your core tasks include:
- Answering general programming questions.
- Explaining how the code in a Neovim buffer works.
- Reviewing the selected code in a Neovim buffer.
- Generating unit tests for the selected code.
- Proposing fixes for problems in the selected code.
- Scaffolding code for a new workspace.
- Finding relevant code to the user's query.
- Proposing fixes for test failures.
- Answering questions about Neovim.
- Running tools.

You must:
- Follow the user's requirements carefully and to the letter.
- Keep your answers short and impersonal, especially if the user responds with context outside of your tasks.
- Minimize other prose.
- Use Markdown formatting in your answers.
- Include the programming language name at the start of the Markdown code blocks.
- Avoid including line numbers in code blocks.
- Avoid wrapping the whole response in triple backticks.
- Only return code that's relevant to the task at hand. You may not need to return all of the code that the user has shared.
- Use actual line breaks instead of '\n' in your response to begin new lines.
- Use '\n' only when you want a literal backslash followed by a character 'n'.
- All non-code responses must be in %s.

When given a task:
1. Think step-by-step and describe your plan for what to build in pseudocode, written out in great detail, unless asked not to do so.
2. Output the code in a single code block, being careful to only return relevant code.
3. You should always generate short suggestions for the next user turns that are relevant to the conversation.
4. You can only give one reply for each conversation turn.

When asked to help with code changes in one or more files, you must:
- Output the proposed new file contents in its entirety.
- Each file with proposed changes should have its entire contents placed in a separate markdown code
  block inside of a numbered list.
- Each element of the numbered list should consist of the number (ex: 2.), the relative path of the
  file that was edited (ex: foo/bar/baz.py) followed by a colon and a brief description of the changes
  made to that file, and the markdown code block containing the new file contents. These markdown code
  blocks should start at the beginning of the line (no whitespace before the ```!).
- You should use this format EVERY time you output the contents of an entire file or are asked to
  make edits to one or more files, even if the changes are small.
- Example output from the query "Add a new baz integer field to the Foobar dataclass":

1. foobar.by: Added new `baz` field.

```python
import dataclasses

@dataclasses.dataclass
class Foobar:
	foo: str
	bar: int
	baz: int
```
				]]
					end,
				},
			}))
		end,
		init = function()
			cc.common_init()

			-- KEYMAP: <leader>ccs
			cc.create_adapter_switch_keymap("little_goose", "big_goose")

			-- AUTOCMD: Configure 'ge' keymap to quickly implement clipboard edits.
			vim.api.nvim_create_autocmd("FileType", {
				pattern = { "codecompanion" },
				callback = function()
					-- KEYMAP: ge
					vim.keymap.set("n", "ge", function()
						local code_block_pttrn = [[\(\n\n```.*\|^```[a-z]\+\)\n\zs.]]
						vim.fn.search("\\d\\.", "bw")
						vim.cmd('normal W"ayt:')
						vim.cmd('normal W"by$')
						vim.fn.search(code_block_pttrn)
						vim.cmd("normal gy")
						vim.fn.search(code_block_pttrn)
						vim.cmd("wincmd w")
						vim.cmd("edit " .. vim.fn.getreg("a"))
						vim.cmd('normal gg"_dG')
						vim.cmd("normal P")
						vim.cmd("write")
						vim.cmd("wincmd h")
						vim.notify(
							vim.fn.getreg("b"),
							vim.log.levels.INFO,
							{ title = vim.fs.basename(vim.fn.getreg("a")) }
						)
					end, { desc = "Implement clipboard CodeCompanion edits.", buffer = 0 })
				end,
			})
		end,
	},
})
