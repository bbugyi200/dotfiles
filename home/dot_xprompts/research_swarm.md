---
description: Launch two independent research agents, consolidate their findings, and generate an infographic.
input:
  - name: prompt
    type: text
    description: Research topic or question for the swarm to investigate.
---

%name:research.@.cdx %model:@research %g:research {{ prompt }} #research

---

%name:research.@.cld %m:@research_assist %g:research {{ prompt }} #research

---

%name:research.@.final %m:@research %wait:research.@.cdx %wait:research.@.cld %g:research

The two independent research agents have finished. Their chat transcript paths are available here:

{% raw %}{{ wait_chats }}{% endraw %}

Read both chat transcripts first. From those transcripts, identify the two `sdd/research/` markdown files created by the
agents, then read both files.

Verify the prior work against the request below. Consolidate and improve the research into one final `sdd/research/`
markdown file without unnecessary length growth. Preserve the strongest findings, resolve conflicts, add any missing
critical context, and remove duplication.

After the final consolidated research file exists, delete the two intermediate `sdd/research/` markdown files created by
the prior agents.

Research request:

{{ prompt }}

---

%name:research.@.image %model:codex/gpt-5.5 %wait:research.@.final %g:research #fork:research.@.final #research/image
