---
name: split_executor
input:
  {
    diff_path: path,
    spec_markdown: text,
    default_parent: word,
    bug_flag: 'line = ""',
    note: line,
    processing_order: text,
  }
---

Can you help me replicate the changes shown in the @{{ diff_path }} file EXACTLY by splitting the changes across
multiple new CLs (specified below)?

## Split Specification

{{ spec_markdown }}

## Instructions

For each entry in the split specification (process in the order shown - parents before children):

1. **Navigate to the parent CL:**
   - If `parent` is specified in the entry: run `bb_hg_update <parent>`
   - Otherwise: run `bb_hg_update {{ default_parent }}`

2. **Make the file changes for this CL based on its description.**
   - Analyze the original diff and determine which changes belong to this CL
   - Use the description to understand what this CL should contain
   - Apply EXACTLY the portions of the diff that logically belong to this CL

3. **Create the description file** at `bb/gai/<name>_desc.txt` with the description from the spec.

4. **Run:** `gai commit {{ bug_flag }}-n "{{ note }}" <name> bb/gai/<name>_desc.txt`

5. **Repeat** for the next entry.

## Processing Order

Process the entries in this order (parents before children):

{{ processing_order }}
