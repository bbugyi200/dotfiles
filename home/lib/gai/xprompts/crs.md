---
name: crs
input: { critique_comments_path: path, context_files_section: { type: text, default: "" } }
---

Can you help me address the Critique comments? Read all of the files below VERY carefully to make sure that the changes
you make align with the overall goal of this CL! Make the necessary file changes, but do NOT amend/upload the CL.

#cl

<!-- prettier-ignore -->
+ @{{ critique_comments_path }} - Unresolved Critique comments left on this CL (these are the comments you should address!)
{% if context_files_section %}
{{ context_files_section }}{% endif %}
