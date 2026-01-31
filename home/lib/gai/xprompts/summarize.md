---
name: summarize
input:
  - name: target_file
    type: path
  - name: usage
    type: line
---

Can you help me summarize the @${target_file} file in <=30 words (preferably <=25 or even <=15 words)? This summary will
be used as ${usage}.

IMPORTANT: Output ONLY the summary itself, with no additional text, prefixes, or explanations.
