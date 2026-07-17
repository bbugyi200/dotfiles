---
description:
  Launch two independent research agents, then have a lead researcher extend and consolidate their findings and generate
  an infographic.
input:
  - name: prompt
    type: text
    description: Research topic or question for the swarm to investigate.
---

%name:research.@.cdx %model:@research_a %g:research %family(research.@.final, role=researcher) {{ prompt }} #research

---

%name:research.@.cld %m:@research_b %g:research %family(research.@.final, role=researcher) {{ prompt }} #research

---

%name:research.@.final %m:@research_lead %wait:research.@.cdx %wait:research.@.cld %g:research

You are the lead researcher: two independent researchers have reported on the request below, and you will add your own
research and merge all three perspectives into one consolidated report.

Research request:

{{ prompt }}

The researchers' chat transcripts:

{% raw %}{{ wait_chats }}{% endraw %}

Month directory (create it if missing):

$(sase repo path research --ensure)/$(date +%Y%m)

Steps:

1. Read both transcripts to learn which report file each researcher wrote (`research.@.cdx` -> `__a`, `research.@.cld`
   -> `__b`), then read both reports. Never assign `__a`/`__b` from filesystem order.
2. Research the request yourself, prioritizing gaps, weak evidence, and disagreements between the two reports.
3. Pick a descriptive stem `<name>` that collides with nothing in the month directory, create `<month-dir>/<name>/`, and
   move the two reports to `<name>__a.md` and `<name>__b.md` inside it. Preserve both files and never overwrite: on any
   collision, pick a different stem first.
4. Write the consolidated report to `<name>/<name>.md`: merge the strongest findings from both reports and your own
   research, resolve conflicts, cut duplication, and add missing critical context without unnecessary length.

Final layout:

```text
<month-dir>/<name>/
├── <name>__a.md
├── <name>__b.md
└── <name>.md
```

---

%name:research.@.image %model:codex/gpt-5.6-sol %wait:research.@.final %g:research %family(research.@.final, role=image)
#fork:research.@.final #research/image
