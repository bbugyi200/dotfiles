---
description: Launch two independent research agents, consolidate their findings, and generate an infographic.
input:
  - name: prompt
    type: text
    description: Research topic or question for the swarm to investigate.
---

%name:research.@.cdx %model:@research_a %g:research {{ prompt }} #research

---

%name:research.@.cld %m:@research_b %g:research {{ prompt }} #research

---

%name:research.@.final %m:@research_lead %wait:research.@.cdx %wait:research.@.cld %g:research

The two independent research agents have finished. Their chat transcript paths are available here:

{% raw %}{{ wait_chats }}{% endraw %}

Read both chat transcripts first. From those transcripts, identify which markdown file in the effective research
directory was created by the first (`research.@.cdx` / `research_a`) agent and which was created by the second
(`research.@.cld` / `research_b`) agent, then read both files. Keep this producer-to-report association explicit so the
source reports are assigned deterministically rather than by filesystem ordering.

Effective research directory:

$(sase sdd path research --ensure)

Before moving or writing any files, choose a descriptive final markdown filename `<name>.md` and derive `<name>` by
removing its `.md` suffix. The completed layout must be:

```text
<effective-research-directory>/
└── <name>/
    ├── <name>__a.md
    ├── <name>__b.md
    └── <name>.md
```

Do not silently overwrite an existing `<name>` directory or any destination file. If the chosen stem would collide,
select a distinct descriptive stem before moving anything. Once the stem is collision-free, create
`<effective-research-directory>/<name>/` and safely move and rename the first agent's report to `<name>/<name>__a.md`
and the second agent's report to `<name>/<name>__b.md`. Preserve both source reports.

After both source reports have been safely relocated, verify the prior work against the request below. Consolidate and
improve the research into `<name>/<name>.md` without unnecessary length growth. Preserve the strongest findings, resolve
conflicts, add any missing critical context, and remove duplication.

Research request:

{{ prompt }}

---

%name:research.@.image %model:codex/gpt-5.6-sol %wait:research.@.final %g:research #fork:research.@.final
#research/image
